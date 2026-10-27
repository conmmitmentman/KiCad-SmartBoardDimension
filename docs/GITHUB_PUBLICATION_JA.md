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

ネイティブ版は `native-source-v1.0.0` の正式なソースReleaseとしてZIPとSHA256を公開します。Source Preview 1は過去の試作版として保持し、公開済みタグやアセットを置き換えません。新しい版は `tools/build_native_release.py` の `VERSION` を増やし、検証記録と公開文を更新します。

公開前に、対象のクリーンなKiCadソースへ適用し、C++ビルド・回帰テスト・実画面のクリック入力、Undo/Redo、保存・再起動、スナップ配置を確認します。GitHub ActionsではKiCad本体のC++ビルドやGUIテストは実行しません。ローカルの検証結果と未確認項目を `native/README.md` に記録してください。

ネイティブSource Releaseは `--latest=false` で作成し、Python版の自動更新が使う `/releases/latest` はPython版を維持します。公開後は `prerelease=false`、対象コミット、添付ZIPとSHA256、`/releases/latest` がPython版を指すことを確認します。ソース版を正式Releaseにしても、通常のPythonインストーラーにネイティブ機能は入りません。コンパイル済みアプリを配布する場合は、別途ランタイム・ライセンス・導入テストが必要です。

手動公開する場合は、検証済みコミットに `vX.Y.Z` タグを付け、同じバージョンのZIPと `.sha256` を正式Releaseへ添付してください。

[READMEへ戻る](../README.md)
