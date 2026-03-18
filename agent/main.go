package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"
)

// Config models
type NodeRegisterReq struct {
	Hostname      string `json:"hostname"`
	IpAddress     string `json:"ip_address"`
	CapacityRamMb int    `json:"capacity_ram_mb"`
	CapacityVcpus int    `json:"capacity_vcpus"`
}

type NodeResponse struct {
	ID        int    `json:"id"`
	Status    string `json:"status"`
	Heartbeat string `json:"heartbeat"`
}

type TaskResponse struct {
	ID        int    `json:"id"`
	Type      string `json:"type"`
	Payload   string `json:"payload"`
	Status    string `json:"status"`
	CreatedAt string `json:"created_at"`
}

type TaskResultUpdate struct {
	Result string `json:"result"`
}

var serverURL string
var nodeID int

func init() {
	serverURL = os.Getenv("SERVER_URL")
	if serverURL == "" {
		serverURL = "http://10.0.0.1:8000" // Default to WireGuard server IP
	}
}

func main() {
	log.Println("Starting Node Agent...")

	// 1. Bring up WireGuard
	err := setupWireGuard()
	if err != nil {
		log.Fatalf("Failed to setup WireGuard: %v", err)
	}

	// 2. Register with server
	err = registerNode()
	if err != nil {
		log.Fatalf("Failed to register node: %v", err)
	}

	// Start ping goroutine
	go func() {
		for {
			time.Sleep(15 * time.Second)
			pingURL := fmt.Sprintf("%s/node/%d/ping", serverURL, nodeID)
			resp, err := http.Post(pingURL, "application/json", bytes.NewBuffer([]byte{}))
			if err == nil {
				resp.Body.Close()
			}
		}
	}()

	// 3. Poll loop
	log.Println("Beginning task polling loop...")
	for {
		pollTask()
		time.Sleep(3 * time.Second)
	}
}

func setupWireGuard() error {
	log.Println("Setting up WireGuard...")
	// Assuming wg0.conf is injected into /etc/wireguard/wg0.conf
	if _, err := os.Stat("/etc/wireguard/wg0.conf"); os.IsNotExist(err) {
		log.Println("No WireGuard config found at /etc/wireguard/wg0.conf, skipping wg-quick")
		return nil
	}

	cmd := exec.Command("wg-quick", "up", "wg0")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("wg-quick up wg0 failed: %w", err)
	}
	log.Println("WireGuard interface wg0 is up.")
	return nil
}

func registerNode() error {
	hostname, _ := os.Hostname()
	
	// Get WG IP or fallback
	ip := getInterfaceIP("wg0")
	if ip == "" {
		ip = getInterfaceIP("eth0")
	}
	if ip == "" {
		ip = "127.0.0.1"
	}

	reqData := NodeRegisterReq{
		Hostname:      hostname,
		IpAddress:     ip,
		CapacityRamMb: 128,
		CapacityVcpus: 1,
	}

	jsonData, _ := json.Marshal(reqData)
	resp, err := http.Post(serverURL+"/node/register", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("server returned status code %d", resp.StatusCode)
	}

	var nodeResp NodeResponse
	if err := json.NewDecoder(resp.Body).Decode(&nodeResp); err != nil {
		return err
	}

	nodeID = nodeResp.ID
	log.Printf("Successfully registered with server. Node ID: %d", nodeID)
	return nil
}

func getInterfaceIP(iface string) string {
	cmd := exec.Command("ip", "-4", "-o", "addr", "show", "dev", iface)
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	
	// Output looks like: "2: wg0    inet 10.0.0.101/24 scope global wg0\n..."
	parts := strings.Fields(string(out))
	for i, part := range parts {
		if part == "inet" && i+1 < len(parts) {
			ipWithCidr := parts[i+1]
			ip := strings.Split(ipWithCidr, "/")[0]
			return ip
		}
	}
	return ""
}

func pollTask() {
	url := fmt.Sprintf("%s/task/next?node_id=%d", serverURL, nodeID)
	resp, err := http.Get(url)
	if err != nil {
		log.Printf("Error polling for task: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return // No task or error
	}

	var task TaskResponse
	body, _ := ioutil.ReadAll(resp.Body)

	// If body is empty or null, no task
	if len(body) == 0 || string(body) == "null" {
		return
	}

	err = json.Unmarshal(body, &task)
	if err != nil {
		log.Printf("Error unmarshaling task: %v", err)
		return
	}

	log.Printf("Received task %d: %s", task.ID, task.Type)
	executeTask(task)
}

type SafeBuffer struct {
	buf bytes.Buffer
	mu  sync.Mutex
}

func (b *SafeBuffer) Write(p []byte) (n int, err error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *SafeBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

func executeTask(task TaskResponse) {
	var result string

	if task.Type == "agent_cmd" {
		var payloadData map[string]string
		if err := json.Unmarshal([]byte(task.Payload), &payloadData); err == nil {
			if code, exists := payloadData["code"]; exists {
				cmd := exec.Command("sh", "-c", code)
				
				var outBuf SafeBuffer
				cmd.Stdout = &outBuf
				cmd.Stderr = &outBuf

				if err := cmd.Start(); err != nil {
					result = fmt.Sprintf("Error starting command: %v", err)
				} else {
					// Checkpoint loop
					done := make(chan error, 1)
					go func() {
						done <- cmd.Wait()
					}()

					ticker := time.NewTicker(3 * time.Second)
					defer ticker.Stop()

				waitloop:
					for {
						select {
						case err := <-done:
							if err != nil {
								result = fmt.Sprintf("Error: %v\nOutput: %s", err, outBuf.String())
							} else {
								result = outBuf.String()
							}
							break waitloop
						case <-ticker.C:
							// Send checkpoint
							sendCheckpoint(task.ID, outBuf.String())
						}
					}
				}
			} else {
				result = "Error: no 'code' in payload"
			}
		} else {
			result = fmt.Sprintf("Error parsing payload: %v", err)
		}
	} else {
		result = fmt.Sprintf("Unknown task type: %s", task.Type)
	}

	log.Printf("Task %d completed. Result length: %d", task.ID, len(result))

	// Send result
	resData := TaskResultUpdate{Result: result}
	jsonRes, _ := json.Marshal(resData)
	url := fmt.Sprintf("%s/task/%d/result", serverURL, task.ID)
	
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonRes))
	if err != nil {
		log.Printf("Failed to send task result: %v", err)
		return
	}
	defer resp.Body.Close()
	log.Printf("Task %d result successfully reported.", task.ID)
}

type TaskCheckpointUpdate struct {
	Checkpoint string `json:"checkpoint"`
}

func sendCheckpoint(taskID int, data string) {
	cpData := TaskCheckpointUpdate{Checkpoint: data}
	jsonCp, _ := json.Marshal(cpData)
	url := fmt.Sprintf("%s/task/%d/checkpoint", serverURL, taskID)
	
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(jsonCp))
	if err != nil {
		log.Printf("Failed to send checkpoint for task %d: %v", taskID, err)
		return
	}
	defer resp.Body.Close()
	log.Printf("Task %d checkpoint reported (len %d)", taskID, len(data))
}
