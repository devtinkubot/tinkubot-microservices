package metawebhook

type webhookEvent struct {
	Object string  `json:"object"`
	Entry  []entry `json:"entry"`
}

type entry struct {
	ID      string   `json:"id"`
	Changes []change `json:"changes"`
}

type change struct {
	Field string      `json:"field"`
	Value changeValue `json:"value"`
}

type changeValue struct {
	Metadata metaMetadata  `json:"metadata"`
	Messages []metaMessage `json:"messages"`
	Statuses []interface{} `json:"statuses"`
	Contacts []interface{} `json:"contacts"`
}

type metaMetadata struct {
	PhoneNumberID string `json:"phone_number_id"`
}

type metaMessage struct {
	From      string    `json:"from"`
	ID        string    `json:"id"`
	Timestamp string    `json:"timestamp"`
	Type      string    `json:"type"`
	Text      *metaText `json:"text,omitempty"`
}

type metaText struct {
	Body string `json:"body"`
}

type incomingMessage struct {
	PhoneNumberID string
	From          string
	Message       string
}

func extractIncomingMessages(evt webhookEvent) []incomingMessage {
	out := make([]incomingMessage, 0)
	for _, e := range evt.Entry {
		for _, ch := range e.Changes {
			if ch.Field != "messages" {
				continue
			}
			phoneNumberID := ch.Value.Metadata.PhoneNumberID
			for _, msg := range ch.Value.Messages {
				if msg.From == "" {
					continue
				}
				text := extractMessageText(msg)
				if text == "" {
					continue
				}
				out = append(out, incomingMessage{
					PhoneNumberID: phoneNumberID,
					From:          msg.From,
					Message:       text,
				})
			}
		}
	}
	return out
}

func extractMessageText(msg metaMessage) string {
	if msg.Type == "text" && msg.Text != nil {
		return msg.Text.Body
	}
	if msg.Text != nil && msg.Text.Body != "" {
		return msg.Text.Body
	}
	return ""
}
