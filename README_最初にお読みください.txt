スマート基板寸法 KiCad 10 / v1.3.0 開発版

このインストーラーはPythonプラグイン版です。
プラグインを起動後、PCB上の寸法数字をクリックして数値・計算式を入力できます。
PCBを開くたびにプラグインを起動します。「詳細・更新」から補助画面を開きます。

毎回の起動操作を不要にするC++ネイティブ版は別途開発・ビルド検証中です。
通常のプラグインインストールでは導入されません。README.mdの開発状況を参照してください。

【追加機能】KiCadのダイアログ内に「GitHubから更新」「更新元の設定」ボタンを追加しました。
更新先はconmmitmentman/KiCad-SmartBoardDimensionを設定済みです。「GitHubから更新」を押せば確認・適用できます。
公開済みのGitHub Releaseが必要です。更新後はKiCad PCBエディタを再起動してください。

インストール: Windows_インストール.bat
既にインストール済みで更新: Windows_更新.bat
前のバージョンに戻す: Windows_前の版に戻す.bat

重要:
  1. ZIPをすべて展開し、KiCad PCBエディタを終了してから実行してください。
  2. 基板の .kicad_pcb ファイルをバックアップしてください。
  3. 完了後にKiCad PCBエディタを起動してください。
  4. ツール > 外部プラグイン > スマート基板寸法（幅・高さ）

対応: KiCad 10.x / Windows 10, 11 想定
制限: 軸に平行な長方形のEdge.Cuts外形のみ（複雑な外形は不可）
確認: Windows / KiCad 10.0.7で検証。詳細はdocs/VALIDATION_JA.mdを参照。
      ドキュメントに書き込めない場合はAppDataの探索先を利用します。
      配布ZIPは未署名です。信用できる公開元から取得してください。
      組織やWindowsの設定でPowerShellが禁止される場合は手動コピーしてください。

詳しい説明: README.md, docs/INSTALL_JA.md, docs/UPDATE_JA.md, docs/ONLINE_UPDATE_JA.md
