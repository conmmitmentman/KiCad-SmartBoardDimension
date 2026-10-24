# GitHubへの公開手順（日本語）

この文書は**あなた自身のGitHubアカウントで公開するための手順**です。この配布物を生成しただけでは、GitHub上にリポジトリは作成されません。

## 方法A：ブラウザだけで公開する

1. [GitHub](https://github.com/) にサインインします。
2. 右上の `+` → **New repository** を選びます。
3. Repository name に `KiCad10-SmartBoardDimension` など好きな名前を入力します。
4. Public / Private を選びます。公開前に不要な個人情報・機密ファイルが含まれていないことを確認してください。
5. **Add a README** は選ばずに作成します（本リポジトリには `README.md` が含まれるため）。
6. 作成したリポジトリの **uploading an existing file** または **Add file → Upload files** から、このアーカイブの**中身のファイルとフォルダ**をアップロードします。アップロード先の最上位に `README.md` / `smart_board_dimension/` / `docs/` が並ぶようにします。
7. **Commit changes** を選択します。

**注意**：ブラウザのフォルダアップロードではドラッグ＆ドロップ等の対応がブラウザによって異なります。`.github/` など隠しフォルダを含め確実にアップロードするには、下記のGit方式が推奨です。

## 方法B：Gitを使用（推奨）

PCに [Git](https://git-scm.com/) をインストールし、ZIPを展開したリポジトリ直下でターミナルを開きます。

```bash
git init
git add .
git commit -m "Initial release: Smart Board Dimension v1.2.0"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

`YOUR_ACCOUNT` と `YOUR_REPOSITORY` は**ご自身の値**に置き換えてください。初回はGitの名前・メールアドレス設定やGitHubの認証が必要です。すでに設定済みなら不要です。

## READMEの表示とGitHub Actions

- リポジトリのトップで `README.md` が自動表示されます。
- `.github/workflows/tests.yml` がアップロードされていれば、`Actions` タブでPythonテスト・Release ZIP作成のCIが動きます。
- ソースだけを公開しても、**KiCad Plugin and Content Manager（PCM）へ自動登録されるわけではありません**。

## GitHub ReleaseにインストールZIPを添付する

まずローカルでテスト・パッケージ生成を行います。

```bash
python -m unittest discover -s tests -v
python tools/build_release.py
```

`dist/KiCad10_SmartBoardDimension_v1.2.0_Windows.zip` と検証用の `.sha256` が生成されます。

**手動で公開する場合**：GitHubリポジトリ → **Releases → Draft a new release** → `v1.2.0` のタグを付ける → ZIPを添付 → リリースノート（`CHANGELOG.md` の内容）を書く → Publish release。

**タグで自動生成する場合**：`v1.2.0` タグをpushすると `.github/workflows/release.yml` がZIPを生成し、**ドラフト**のGitHub Releaseを作成します。ドラフトの説明とZIPを確認してから、手動で公開してください。

```bash
git tag v1.2.0
git push origin v1.2.0
```

タグ名と `PLUGIN_VERSION` は一致させてください。タグをpushする前にコードが確定しているかを確認し、GitHub Actions実行権限やRepository SettingsでWorkflow permissionsを確認します。

## 今後の更新手順

- コード修正 → テスト追加 → `PLUGIN_VERSION` 更新 → `CHANGELOG.md` 更新 → commit/push
- GitHub Releaseで新しいZIPとSHA256を添付し、**ドラフトではなく公開**する
- v1.2.0以降の利用者はKiCadの「GitHubから更新」ボタンで更新確認・適用（初回だけ更新元URL登録）
- 更新ボタンを使わない場合、新版 ZIP内の `Windows_更新.bat` でも手動で更新できます
- 問題が出た場合は `Windows_前の版に戻す.bat` で以前の版へ戻す

## リポジトリを公開したら行う設定（更新ボタン）

`smart_board_dimension/updater.py` の `DEFAULT_REPOSITORY = ''` を `DEFAULT_REPOSITORY = 'YOUR_ACCOUNT/YOUR_REPOSITORY'` としてリポジトリの名前を登録することをおすすめします。**リポジトリの名前が決まるまで空欄でも問題ありません**。空欄の場合、利用者の初回更新時にURLの入力が必要です。

GitHub APIが参照するのは公開済みの正式Releaseです。**ソースだけのpush、タグだけのpush、ドラフトReleaseだけでは更新ボタンに新バージョンは表示されません。** テスト方法も含めて [GitHubからの更新ガイド](ONLINE_UPDATE_JA.md) を参照してください。

## 推奨リポジトリ設定

- Description：`KiCad 10向け日本語PCB外形寸法編集プラグイン（Edge.Cuts長方形）`
- Topics例：`kicad`, `kicad-plugin`, `pcb`, `python`, `japanese`
- License：MIT（含まれている `LICENSE` を使用）
- Issues：有効（バグ報告・機能要望のテンプレートを用意済み）
- 重要：KiCad実機テスト済みと誤認されないよう、READMEの未検証表示は確認が終わるまで削除しない

[READMEへ戻る](../README.md)
