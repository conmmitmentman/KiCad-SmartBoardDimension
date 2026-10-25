# GitHubから更新（KiCad内ワンクリック更新）

## 対応バージョンと現在の状況

**スマート基板寸法 v1.2.0 以降**に、KiCad内から更新を確認して適用するボタンがあります。既存の v1.1.0 以前の環境にはボタンがないため、**v1.3.0 の ZIP を手動導入**してください。

> 寸法編集の検証範囲は[実機検証記録](VALIDATION_JA.md)を参照してください。正式ReleaseとZIPが公開されると、既定の更新先から取得できます。

## 利用者：更新する方法

1. KiCad 10のPCBエディタを開き、**ツール → 外部プラグイン → スマート基板寸法（幅・高さ）** を起動します。
2. ダイアログ下部の **「GitHubから更新」** を押します。
3. 既定の更新先は `conmmitmentman/KiCad-SmartBoardDimension` です。変更する場合だけ「更新元の設定」を使います。
4. 新バージョンが見つかったら、確認画面の「はい」をクリックします。
5. GitHubからZIPをダウンロードし、チェックサム・ファイル構成の検査と更新前バックアップを行います。
6. 更新完了メッセージが表示されたら、**編集中のPCBを保存してKiCad PCBエディタを終了し、もう一度起動**します。

新版が見つからなければ「最新版です」と表示します。通信に失敗しても、ダウンロード前なら既存版を変更しません。更新中のダイアログを閉じる操作は制限されます。

### 更新元を変更する

ダイアログの **「更新元の設定」** を押し、正しいURLを登録してください。リポジトリはログイン不要の**公開**リポジトリを使用します。プライベートリポジトリは現時点で非対応です。

ユーザー別の設定保存先（Windows）：

```text
%LOCALAPPDATA%\SmartBoardDimension\settings.json
```

設定に認証トークンやGitHubパスワードは不要で、**保存しません**。ネットワーク通信はボタン操作時だけ行われます（定期的な自動チェックは行いません）。

## 更新元リポジトリを公開する方

この配布版では `DEFAULT_REPOSITORY` を設定済みです。派生版を配布する場合は、次の方法で変更します。

- **方法A：** `smart_board_dimension/updater.py` の `DEFAULT_REPOSITORY` を `DEFAULT_REPOSITORY = 'OWNER/REPOSITORY'` に変更してからGitHubにコミット・Releaseを作成します。これで利用者は初回のURL登録なしで更新確認できます。
- **方法B：** `DEFAULT_REPOSITORY = ''` に変更します。利用者が初回更新時にURLを登録します。リポジトリ名が未確定ならこちらを使用します。

**ユーザーが登録した更新元（settings.json）を優先**し、`DEFAULT_REPOSITORY` は初期値としてのみ機能します。

### GitHub Releaseの公開方法

1. プラグインの `PLUGIN_VERSION` を増やし、`CHANGELOG.md` とテストを更新します。
2. `python -m unittest discover -s tests -v` で検証します。
3. `python tools/build_release.py` で次のファイルを生成します。

   - `dist/KiCad10_SmartBoardDimension_vX.Y.Z_Windows.zip`
   - `dist/KiCad10_SmartBoardDimension_vX.Y.Z_Windows.zip.sha256`

4. 対応する `vX.Y.Z` タグでGitHub Releaseを作り、上記2ファイルをアセットに登録して**公開**します（Draftのままでは更新先になりません）。
5. 自動更新から正常に取得できることを、別PCやテスト環境で確認します。mainへの反映時に公開ワークフローがテストと配布物検証を行い、未公開のバージョンをReleaseにします。公開済みの同じバージョンを上書きしません。

GitHub REST API `GET /repos/{owner}/{repo}/releases/latest` を利用するため、**リポジトリにタグだけを追加しても更新できません**。**公開済みの正式Release**と、命名規則に合ったZIPアセットが必要です。

## チェック内容

- GitHub APIの公開Release情報と、インストール済みとの **数値的バージョン比較**（`1.2.0` など）
- 配布ZIPのサイズ制限（12 MiB）と、GitHub API の`digest`、またはRelease添付の `.sha256` との照合
- ZIP内の `update_manifest.json`（バージョン・各PythonファイルのSHA256）との照合
- 想定された `smart_board_dimension/*.py` のみ取り出し（任意のパス展開を禁止）
- 更新対象Pythonファイルの構文、バージョン定義の照合
- 更新前に `.py` ファイルをバックアップし、置換失敗時には置換したファイルを復元

**注意：** チェックサムは通信破損・ファイル不一致の検知に役立ちますが、**GitHubリポジトリ自体が侵害された場合や管理者が意図的に変更したコードを防ぐものではありません**。電子署名や外部の信頼鍵による検証は現状未実装です。

## 以前のバージョンに戻す

KiCadのPCBエディタを終了し、配布ZIP内の **`Windows_前の版に戻す.bat`** を実行します。バックアップは次の場所に保存されます。

```text
%LOCALAPPDATA%\SmartBoardDimension\backups\
```

オフライン更新とオンライン更新の両方が同じバックアップ先を使用します。バックアップ内の `metadata.json` には更新前のバージョンが記録されます。**PCBデータ自体はバックアップしない**ので基板ファイルは別途保管してください。

## 更新ができないとき

- **404／Releaseが見つからない：** リポジトリURL、GitHubの公開設定、正式Releaseの公開状態をご確認ください。
- **ZIPが見つからない：** アセット名 `KiCad10_SmartBoardDimension_vX.Y.Z_Windows.zip` を確認してください。
- **チェックサムエラー：** ZIPの内容を適用しません。Releaseアセットを再作成・再アップロードしてください。
- **ファイル書き込み権限エラー：** KiCadを終了し、手動の `Windows_更新.bat` で試してください。
- **バージョンが既に最新：** 正常です。旧版に下げる用途にはオンライン更新を利用できません。

詳細：[オフライン更新と復元](UPDATE_JA.md)、[トラブルシューティング](TROUBLESHOOTING_JA.md)
