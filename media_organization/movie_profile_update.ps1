# Get the existing profile
$profile = Invoke-RestMethod `
  -Uri "http://192.168.10.25:7878/api/v3/qualityprofile/1" `
  -Method Get `
  -Headers @{ "X-Api-Key" = "5c37a6eba340440baefee1376d650366" }

# Modify it
$profile.name = "1080p+ Upgradable"
$profile.upgradeAllowed = $true
$profile.cutoff = 14

# Set which qualities are allowed
foreach ($item in $profile.items) {
    $qualityId = $item.quality.id
    # Allow qualities 9-17 (720p through 2160p)
    $item.allowed = ($qualityId -ge 9 -and $qualityId -le 17)
}

# Create as new profile (remove the ID)
$profile.PSObject.Properties.Remove('id')

# Post it
$profile | ConvertTo-Json -Depth 10 | Out-File "C:\temp\new_profile.json"
Invoke-RestMethod `
  -Uri "http://192.168.10.25:7878/api/v3/qualityprofile" `
  -Method Post `
  -Headers @{ "X-Api-Key" = "5c37a6eba340440baefee1376d650366" } `
  -ContentType "application/json" `
  -Body ($profile | ConvertTo-Json -Depth 10)