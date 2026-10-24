# セキュリティ / Security

## 取扱い上の注意

- ZIPは信頼できる配布元から入手してください。ファイルは未署名です。
- `Windows_インストール.bat` / `Windows_更新.bat` / `Windows_前の版に戻す.bat` はローカルの PowerShell スクリプトを実行します。**管理者権限・外部通信は不要**です。
- インストーラーはユーザーごとの KiCad プラグインフォルダに `__init__.py` と `geometry.py` を配置し、更新前には `%LOCALAPPDATA%\SmartBoardDimension\backups` にコピーを残します。
- `KiCad` 本体、プロジェクト、部品・配線データをバックアップする仕組みではありません。
- 不明な更新ファイルを実行したり、プラグインを信頼できないサイトから取得したりしないでください。

## 脆弱性の報告

パブリックIssueにパスワード・トークン・個人情報・未公開基板データを貼らないでください。リポジトリ公開後、GitHubの **Security → Report a vulnerability** / Private vulnerability reporting が利用可能なら、そちらから報告してください。機能が未設定なら、公開可能な範囲の概要をIssueで伝え、詳細の公開は避けてください。

現時点でソフトウェアの外部セキュリティ監査・コード署名は実施していません。
