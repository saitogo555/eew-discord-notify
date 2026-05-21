# eew-discord-notify

P2P地震情報のWebSocket APIを受信し、Discord Webhookに地震情報を通知するシステムです。

## 特徴

- P2P地震情報のWebSocketを監視。
- Discord WebhookへEmbed形式で通知。
- ProductionモードとSandboxモードの2種類を切り替え可能。
- Sandboxモード時は通知タイトルに `[Sandbox Mode]` が付与される。
- MIN_SCALEで通知する震度閾値を調整。
- Docker Composeで簡単に起動。

## 動作要件

- Docker
- Docker Compose

## 環境変数

| 変数名 | 必須 | 既定値 | 説明 |
|---|---|---:|---|
| PRODUCTION | いいえ | false | trueのとき本番WebSocketを使用 |
| P2PQUAKE_WS_URL | いいえ | 自動選択 | 明示指定時はこのURLを優先 |
| MIN_SCALE | いいえ | 本番=40 / Sandbox=-1 | 通知する最小震度（値については下記参照） |
| DISCORD_WEBHOOK_URL | はい | - | Discord Webhook URL |

### MIN_SCALE の指定値

| 値 | 対応する震度 |
|---:|---|
| -1 | 不明（すべて通知） |
| 10 | 震度1以上 |
| 20 | 震度2以上 |
| 30 | 震度3以上 |
| 40 | 震度4以上 |
| 45 | 震度5弱以上未入電以上 |
| 50 | 震度5弱以上 |
| 55 | 震度5強以上 |
| 60 | 震度6弱以上 |
| 65 | 震度6強以上 |
| 70 | 震度7のみ |

## 接続先

- Production: `wss://api.p2pquake.net/v2/ws`
- Sandbox: `wss://api-realtime-sandbox.p2pquake.net/v2/ws`

## 使い方

### 1. リポジトリをクローン

```sh
git clone https://github.com/saitogo555/eew-discord-notify
```

### 2. compose.ymlを編集

最低でも `DISCORD_WEBHOOK_URL` を設定してください。

```yaml
environment:
  PRODUCTION: "true"
  MIN_SCALE: "40"
  DISCORD_WEBHOOK_URL: "https://discord.com/api/webhooks/xxxxx/yyyyy"
```

### 3. 起動

```bash
docker compose up -d
```

### 4. ログ確認

```bash
docker compose logs -f
```

### 5. 停止

```bash
docker compose down
```

## 通知仕様

現在の実装では、P2P地震情報のコード551のメッセージを対象にし、MIN_SCALE未満の震度は通知しません。

Sandboxモード（`PRODUCTION=false`）で動作している場合は、通知のタイトルに `[Sandbox Mode]` が付与されます。

同一イベントの重複通知を避けるため、簡易的な重複判定も入れています。

## ライセンス

MIT License
