param(
    [string]$RepoUrl = "https://github.com/amit496/Video-project.git"
)

git remote set-url origin $RepoUrl
git remote -v

Write-Host ""
Write-Host "Remote reset to plain GitHub URL."
