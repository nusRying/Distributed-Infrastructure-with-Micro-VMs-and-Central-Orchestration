# Milestone 1: MVP Development (Detailed Plan)

## Overview
This document contains the timeline, architectural implementation breakdown, and tech stack decisions for Milestone 1: MVP of the Distributed Infrastructure. It details the completion strategy for integrating Google Colab edge runtimes and locally managed micro-VMs.

## 1. Technological Stack Decisions

| Component | Selected Technology | Justification |
| --------- | ------------------- | ------------- |
| **Control Server** | Python / FastAPI / Pydantic | Provides an async, fast API with robust validation, perfect for handling hundreds of incoming heartbeats and checkpoint logs. |
| **Relational DB** | PostgreSQL & SQLAlchemy | Proven, reliable transactional datastore to lock tasks natively, preventing duplicate task dispatching across agents. |
| **Task Queue** | Redis & python-rq | A lightweight and widely compatible background job processor. Required to orchestrate spinning Colab Playwright instances cleanly outside of the HTTP thread. |
| **Node Agent** | Golang (Go) | Compiled statically. The resulting binaries are extremely small and have zero dependencies, ideal for injecting directly into a 15MB Firecracker Linux root filesystem. |
| **Micro-VM** | Firecracker & Alpine Linux | Built for serverless. Boots in < 125ms. Highly stripped down to execute small arbitrary payloads safely. |
| **Tunneling** | WireGuard | Creates an end-to-end encrypted IP tunnel between the Firecracker instances (which act behind a NAT) and the control server. Fast, in-kernel cryptography. |
| **Browser Runtime**| Playwright Python | Automates connecting to Google Colab environments via browser manipulation to deploy dynamic cells interacting with our API endpoint. |

## 2. Core Architecture Pipeline

### Node Connection Flow
1. `vm-builder/create-vm.sh` scaffolds an Alpine rootfs and extracts the Go `agent`.
2. Firecracker starts via `launch.sh`, attaching the network TUN/TAP to the host NAT's `virbr0`.
3. The Alpine `init` launches `wg-quick` against the pre-generated `wg0.conf`.
4. The agent dials `POST /node/register` over the WG Tunnel IP (`10.0.0.x`).
5. The Control Server logs the Node internally.

### Task Dispatching Flow (Decision Engine)
1. User invokes `POST /task` detailing payload instructions.
2. If `target == vm`, the engine loops over active registered nodes connected over WG.
3. If `target == colab`, an RQ background `launch_colab_worker` job is kicked off which uses Playwright to grab a free Google session, simulating a Node ID.
4. Active nodes hit `GET /node/<id>/task` every few seconds to grab work.

### Failover Resilience 
- The Server has an asyncio polling task looping every 30s (`manage_node_timeouts`).
- If a registered Node goes 60s without pushing a `/heartbeat` payload, it is dynamically marked as `dead`.
- Any tasks currently queued or running on the `dead` node are returned to the `pending` queue.

## 3. Acceptance Verification
All parts of the MVP acceptances are verified against a local Linux workstation running KVM `ls /dev/kvm`. E2E scenarios are achieved utilizing the local FastAPI swagger UI.
