# p2pquake-discord-notify

P2P地震情報のWebSocket APIを受信し、Discord Webhookに地震情報を通知するシステムです。

## 特徴

- P2P地震情報のWebSocketを監視。
- Discord WebhookへEmbed形式で通知。
- ProductinモードとSandboxモードの2種類を切り替え可能。
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
| MIN_SCALE | いいえ | 本番=40 / sandbox=-1 | 通知する最小震度 |
| DISCORD_WEBHOOK_URL | はい | - | Discord Webhook URL |
| DISCORD_USERNAME | いいえ | P2PQuake Notify | 投稿時の表示名 |
| DISCORD_AVATAR_URL | いいえ | 空 | 投稿時のアイコン画像URL |
| LOG_LEVEL | いいえ | INFO | DEBUG、INFOなど |

## 接続先

- Production: `wss://api.p2pquake.net/v2/ws`
- Sandbox: `wss://api-realtime-sandbox.p2pquake.net/v2/ws`

## 使い方

### 1. compose.ymlを編集

最低でも `DISCORD_WEBHOOK_URL` を設定してください。

```yaml
environment:
  PRODUCTION: "true"
  MIN_SCALE: "40"
  DISCORD_WEBHOOK_URL: "https://discord.com/api/webhooks/xxxxx/yyyyy"
  DISCORD_USERNAME: "P2PQuake Notify"
  DISCORD_AVATAR_URL: ""
  LOG_LEVEL: "INFO"
```

### 2. 起動

```bash
docker compose up -d
```

### 3. ログ確認

```bash
docker compose logs -f
```

### 4. 停止

```bash
docker compose down
```

## 通知仕様

現在の実装では、P2P地震情報のコード551のメッセージを対象にし、MIN_SCALE未満の震度は通知しません。

同一イベントの重複通知を避けるため、簡易的な重複判定も入れています。

## ライセンス

MIT License
