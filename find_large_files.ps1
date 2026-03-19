Get-ChildItem -Path C:\ -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object Length -Descending |
    Select-Object -First 20 |
    Select-Object FullName, @{Name='SizeGB';Expression={[math]::Round($_.Length / 1GB, 2)}} |
    Format-Table -AutoSize
