# GitHub公開手順

1. `PLUGIN_VERSION` を増やし、README・CHANGELOG・テストを更新します。
2. `python -m unittest discover -s tests -v` を実行します。
3. WindowsではKiCad付属Pythonで `python tools/check_kicad.py` と実画面の操作確認を行います。
4. `python tools/build_release.py` でZIPとSHA256を生成します。
5. `python tools/publish_release.py --check-only` でソースと配布物の一致を確認します。
6. 検証した変更をmainへ反映します。
7. **Test and publish release** ワークフローがPythonテストとパッチ生成テストを実行し、実行中のコミットから配布ZIPを作り直して検証します。Python版の現在のバージョンが未公開なら正式Releaseを作成します。タグは実行中のコミットを指し、ZIPとSHA256を添付します。
8. Actionsの成功、Releasesのアセット、プラグインの更新確認を確認してください。

公開済みバージョンは上書きしません。修正を配布するときはバージョンを増やしてください。ワークフローはGitHub提供の一時トークンを使用し、個人用トークンの登録は不要です。リポジトリでGitHub Actionsが利用可能である必要があります。

ネイティブ版は `native-source-preview-1` という別のプレリリースとしてソースZIPとSHA256を公開します。Python版の自動更新先にはなりません。GitHub ActionsではKiCad本体のC++ビルドやGUIテストは実行しません。ローカルの検証結果と未確認項目を `native/README.md` に記録してください。次回のネイティブ公開時は、`build_native_release.py` のZIP名と `publish_native_release.py` のタグ・公開文を更新してください。

手動公開する場合は、検証済みコミットに `vX.Y.Z` タグを付け、同じバージョンのZIPと `.sha256` を正式Releaseへ添付してください。

[READMEへ戻る](../README.md)
