param(
  [Parameter(Mandatory=$false)][string]$TaskName = "ProlificGitActive"
)

Write-Host "Deleting Scheduled Task: $TaskName"
schtasks /Delete /F /TN $TaskName | Out-Null
Write-Host "Done."


