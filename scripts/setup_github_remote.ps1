param(
    [string]$GithubToken,

    [string]$TokenFile = "scripts/github_token.txt",

    [string]$RepoUrl = "https://github.com/amit496/Video-project.git"
)

if (-not $GithubToken) {
    if (-not (Test-Path -LiteralPath $TokenFile)) {
        throw "GitHub token not provided. Add token in $TokenFile or pass -GithubToken."
    }
    $GithubToken = (Get-Content -LiteralPath $TokenFile -Raw).Trim()
}

if (-not $GithubToken) {
    throw "GitHub token is empty."
}

$tokenUrl = $RepoUrl -replace "^https://", ("https://" + $GithubToken + "@")

git remote set-url origin $tokenUrl
git remote -v

Write-Host ""
Write-Host "Private GitHub remote configured for push."
Write-Host "You can now run:"
Write-Host "git push -u origin main"
Write-Host ""
Write-Host "After pushing, for safety, switch remote back to plain URL:"
Write-Host ('git remote set-url origin "' + $RepoUrl + '"')
