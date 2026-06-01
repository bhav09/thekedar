# WhatsApp integration

## 1. Meta developer setup

1. [Meta for Developers](https://developers.facebook.com/) → Create app → WhatsApp product
2. Configure a test phone number or production number
3. Set webhook URL: `https://YOUR-TUNNEL/webhooks/whatsapp`
4. Verify token: must match `WHATSAPP_VERIFY_TOKEN` in `.env`

## 2. Environment variables

```bash
WHATSAPP_APP_SECRET=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
```

## 3. Workspace mapping

```yaml
whatsapp_phone_number_id: "YOUR_PHONE_NUMBER_ID"
```

## 4. Tunnel

WhatsApp requires HTTPS. Use `./scripts/tunnel.sh`.

## 5. Test

Send a message to your WhatsApp business number: `@Status`
