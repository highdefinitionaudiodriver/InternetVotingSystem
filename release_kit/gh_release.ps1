# GitHub Release 作成スニペット（PowerShell）。
# 事前に gh auth login 済みであること。タグ未作成なら gh が作成する。
# repo: https://github.com/highdefinitionaudiodriver/InternetVotingSystem
$ver = 'v0.2.0'
$notes = Get-Content -Raw -Encoding UTF8 "$PSScriptRoot\RELEASE_NOTES.md"
gh release create $ver `
  --title "インターネット投票システム $ver" `
  --notes "$notes" `
  # 配布物を添付する場合は末尾にファイルパスを列挙: （添付資産があれば指定）
