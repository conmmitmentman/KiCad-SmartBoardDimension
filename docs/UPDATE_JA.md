# 更新パッチ・復元ガイド（日本語）

## このプロジェクトの「更新パッチ」とは

毎回アンインストールする必要はありません。正式Releaseが公開されればKiCadの「GitHubから更新」を使えます。ZIPからのオフライン更新も利用できます。詳細は [GitHubからの更新ガイド](ONLINE_UPDATE_JA.md) を参照してください。

このページでは、ダウンロード済みのZIPから `.py` ファイルを入れ替える**オフライン更新・旧版復元**を説明します。

## 既存インストールを更新する手順

1. 新バージョンの Release ZIP をダウンロードし、**すべて展開**します。
2. KiCad PCB エディタを終了します。
3. 新しいZIPの中の `Windows_更新.bat` を実行します。
4. 「更新前のバックアップ」「導入完了: vX.Y.Z」の表示を確認します。
5. KiCad PCB エディタを起動して動作を確かめます。

既存プラグインがない場合、更新は実行せずにエラーになります。初回は `Windows_インストール.bat` を使ってください。

## 旧版へ戻す（ロールバック）

1. KiCad PCB エディタを終了します。
2. `Windows_前の版に戻す.bat` を実行します。
3. 最後の更新前に保存された `.py` ファイルが復元されます。
4. KiCadを起動して確認します。

バックアップがなければ復元できません。復元後、そのバックアップは「使用済み」として記録されます。手動でフォルダを移動・改名した場合などは対象が見つからないことがあります。

## 保存場所 / 保護対象

- 対象：ユーザーの `KiCad/10.0/scripting/plugins/smart_board_dimension`
- **バックアップ：`%LOCALAPPDATA%\SmartBoardDimension\backups\日時-識別子\`**
- バックアップするもの：更新前に存在した `__init__.py`、`geometry.py`、`updater.py`、`canvas.py`、`direct_editor.py`（旧版にないファイルは省略）、バックアップメタデータ
- 変更しないもの：`.kicad_pcb`、フットプリント、ネットリスト、配線、個人設定等

更新前の KiCad 基板データは**別途ユーザーがバックアップ**してください。これはプラグインコードの復元機構であり、編集後のPCBデータを元へ戻す仕組みではありません。

## Windowsの「ドキュメント」が移動されている場合

インストーラーはWindowsに登録されている実際の「ドキュメント」フォルダを最初に確認し、通常のドキュメントパスや一部の代替パスから既存プラグインを検出します。複数コピーがある場合は誤更新を避けるため中断します。

場所が特殊なときはWindows PowerShell 5.1以上で以下を実行してください。

```powershell
.\scripts\installer.ps1 -Mode Update -Destination 'C:\任意の配置先\smart_board_dimension'
```

`.ps1` の実行が制限されている場合は、付属の `.bat` を使用するか、使用PCの管理ポリシーに従ってください。組織のセキュリティ設定を変更するよう強制するものではありません。

## 更新を作る開発者向け

1. `smart_board_dimension/__init__.py` の `PLUGIN_VERSION` を変更します。
2. 変更したコードとテストをコミットします。
3. `CHANGELOG.md` に変更点を追記します。
4. `python -m unittest discover -s tests -v` を実行します。
5. `python tools/build_release.py` を実行します（オンライン更新マニフェストもZIP内に自動生成されます）。
6. `dist/KiCad10_SmartBoardDimension_vX.Y.Z_Windows.zip` をGitHub Releasesへ添付します。
7. 新版の更新バッチで **v1.0.0からの更新 → 動作 → ロールバック** をWindows/KiCad実機で検証してください。

**注意**：将来ファイル構成が5ファイルより増える場合、`scripts/installer.ps1` の `$files` と `tools/build_release.py` の `RELEASE_FILES` を更新してください。現時点のオフライン更新は上記5ファイルを扱います。

[READMEへ戻る](../README.md)
