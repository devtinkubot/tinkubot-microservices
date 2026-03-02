package metawebhook

import "strings"

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
	From        string           `json:"from"`
	ID          string           `json:"id"`
	Timestamp   string           `json:"timestamp"`
	Type        string           `json:"type"`
	Text        *metaText        `json:"text,omitempty"`
	Interactive *metaInteractive `json:"interactive,omitempty"`
	Location    *metaLocation    `json:"location,omitempty"`
}

type metaText struct {
	Body string `json:"body"`
}

type metaInteractive struct {
	Type        string                `json:"type"`
	ButtonReply *metaInteractiveReply `json:"button_reply,omitempty"`
	ListReply   *metaInteractiveReply `json:"list_reply,omitempty"`
	NFMReply    *metaNFMReply         `json:"nfm_reply,omitempty"`
}

type metaInteractiveReply struct {
	ID    string `json:"id"`
	Title string `json:"title"`
}

type metaNFMReply struct {
	Name         string         `json:"name,omitempty"`
	Body         string         `json:"body,omitempty"`
	ResponseJSON map[string]any `json:"response_json,omitempty"`
}

type metaLocation struct {
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
	Name      string  `json:"name,omitempty"`
	Address   string  `json:"address,omitempty"`
}

type incomingMessage struct {
	PhoneNumberID  string
	From           string
	Content        string
	MessageType    string
	SelectedOption string
	FlowPayload    map[string]any
	Location       *metaLocation
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
				content, messageType, selectedOption, flowPayload, location := extractMessageData(msg)
				if content == "" && selectedOption == "" && flowPayload == nil && location == nil {
					continue
				}
				out = append(out, incomingMessage{
					PhoneNumberID:  phoneNumberID,
					From:           msg.From,
					Content:        content,
					MessageType:    messageType,
					SelectedOption: selectedOption,
					FlowPayload:    flowPayload,
					Location:       location,
				})
			}
		}
	}
	return out
}

func extractMessageData(msg metaMessage) (content, messageType, selectedOption string, flowPayload map[string]any, location *metaLocation) {
	if msg.Type == "text" && msg.Text != nil {
		return msg.Text.Body, "text", "", nil, nil
	}

	if msg.Type == "interactive" && msg.Interactive != nil {
		if msg.Interactive.ButtonReply != nil {
			selected := strings.TrimSpace(msg.Interactive.ButtonReply.ID)
			if selected != "" {
				return "", "interactive_button_reply", selected, nil, nil
			}
			normalizedTitle := normalizeReplyTitle(msg.Interactive.ButtonReply.Title)
			return "", "interactive_button_reply", normalizedTitle, nil, nil
		}
		if msg.Interactive.ListReply != nil {
			return "", "interactive_list_reply", msg.Interactive.ListReply.ID, nil, nil
		}
		if msg.Interactive.NFMReply != nil {
			selected := msg.Interactive.NFMReply.Name
			return "", "interactive_flow_reply", selected, msg.Interactive.NFMReply.ResponseJSON, nil
		}
	}

	if msg.Type == "location" && msg.Location != nil {
		contentParts := ""
		if msg.Location.Name != "" {
			contentParts = msg.Location.Name
		}
		if msg.Location.Address != "" {
			if contentParts != "" {
				contentParts += ", "
			}
			contentParts += msg.Location.Address
		}
		return contentParts, "location", "", nil, msg.Location
	}

	if msg.Text != nil && msg.Text.Body != "" {
		return msg.Text.Body, "text", "", nil, nil
	}
	return "", "", "", nil, nil
}

func normalizeReplyTitle(raw string) string {
	return strings.ToLower(strings.TrimSpace(raw))
}
