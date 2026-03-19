$dirs = @('Downloads', 'Videos', 'Pictures', 'Documents', 'AppData\Local', 'AppData\Roaming', '.npm', '.cache', '.cargo', '.gradle', 'Desktop')
$results = foreach ($d in $dirs) {
    $path = Join-Path $HOME $d
    if (Test-Path $path) {
        try {
            $size = (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            [PSCustomObject]@{
                Name = $d
                SizeGB = [math]::Round($size / 1GB, 2)
                Path = $path
            }
        } catch {
            [PSCustomObject]@{
                Name = $d
                SizeGB = 0
                Path = $path + " (Error)"
            }
        }
    }
}
$results | Sort-Object SizeGB -Descending | Format-Table -AutoSize
