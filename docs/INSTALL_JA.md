# インストールガイド（日本語）

## 必要なもの

- KiCad 10.x（PCB エディタで動作）
- Windows 10 / 11（付属バッチ対象）、または手動配置が可能な macOS / Linux
- このリポジトリの全ファイル、または Releases の Windows ZIP

### Windows：簡単インストール

1. KiCad PCB エディタを終了します。
2. ZIPファイルを右クリック → **すべて展開**。バッチだけ取り出すのではなく、フォルダ構造のまま展開します。
3. 展開した場所にある `Windows_インストール.bat` をダブルクリックします。
4. 結果に「導入完了」が表示されることを確認します。
5. KiCad 10 → PCB エディタ → **ツール → 外部プラグイン**から起動します。

バッチは `scripts/installer.ps1` を呼び出します。インターネット接続・管理者権限は通常必要ありません。ただしWindowsのPowerShell実行ポリシーによっては実行が制限されます。その場合は無理にポリシーを変更せず、上記の手動インストールを利用してください。既存のプラグインがある場合はインストールでも旧版が自動退避されます。

### Windows：手動インストール

「ドキュメント」へ書き込めない場合は `%APPDATA%\kicad\10.0\scripting\plugins` に配置できます。v1.2.1のインストーラーは新規導入時に書き込みを確認し、この代替先へ切り替えます。既存版がある場合は元の場所を更新します。複数箇所へ重複配置しないでください。終了時の「対象:」のパスを控えてください。

1. ZIPを展開して `smart_board_dimension` フォルダを見つけます。
2. Windows エクスプローラーのアドレスバーへ `%USERPROFILE%\Documents\KiCad\10.0\scripting\plugins` を貼り付けます。
3. その中へ `smart_board_dimension` フォルダを**丸ごと**コピーします。
4. KiCad PCB エディタを再起動します。

Windowsで「ドキュメント」がOneDriveなどへ移動されている場合は、Windowsの実際のドキュメントフォルダ内の `KiCad\10.0\scripting\plugins` を使ってください。プラグインが表示されない場合、KiCad内のPythonコンソールで次を確認できます。

```python
import pcbnew
print(pcbnew.PLUGIN_DIRECTORIES_SEARCH)
```

公式に記載された既定のパスは以下のとおりです。

| OS | KiCad 10 の通常の配置先 |
|---|---|
| Windows | `%USERPROFILE%\Documents\KiCad\10.0\scripting\plugins` |
| macOS | `~/Documents/KiCad/10.0/scripting/plugins` |
| Linux | `~/.local/share/kicad/10.0/scripting/plugins` |

環境ごとの設定変更がある場合は `PLUGIN_DIRECTORIES_SEARCH` で実際の探索先を確認してください。

### macOS / Linux：手動インストール

該当する `scripting/plugins/` を作り、その中に `smart_board_dimension` フォルダをコピーします。KiCadのPCBエディタを再起動します。**Windows用 `.bat` / `.ps1` は使用しません**。

### 確認方法

- メニューに **「スマート基板寸法（幅・高さ）」** があるか
- バックアップした基板の `Edge.Cuts` に軸平行の長方形を置き、寸法変更画面が表示されるか
- 寸法を変更した後、保存とDRCで確認できるか

### 再インストールが必要になる場合

WindowsやKiCadの通常の再起動では不要です。ファイルを手動削除した場合、KiCad 10 のユーザーデータを削除した場合、または別PCで使う場合は再インストールが必要です。

### アンインストール

KiCadを終了し、実際の導入先の `scripting/plugins/smart_board_dimension` フォルダだけを削除します。代替先を使用した場合は `%APPDATA%\kicad\10.0\scripting\plugins\smart_board_dimension` です。更新バックアップは `%LOCALAPPDATA%\SmartBoardDimension\backups`、更新元設定は同じ親フォルダーの `settings.json` です。不要な場合だけ削除してください（他のプラグインや修正版ソースを削除しないでください）。

[READMEへ戻る](../README.md)
