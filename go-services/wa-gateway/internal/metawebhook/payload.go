package metawebhook

import (
	"log"
	"strings"
)

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
	Contacts []metaContact `json:"contacts"`
}

type metaContact struct {
	Profile metaProfile `json:"profile"`
	WAID    string      `json:"wa_id"`
	UserID  string      `json:"user_id,omitempty"` // BSUID - Business-Scoped User ID
}

type metaProfile struct {
	Name        string `json:"name"`
	Username    string `json:"username,omitempty"`
	CountryCode string `json:"country_code,omitempty"`
}

type metaMetadata struct {
	PhoneNumberID string `json:"phone_number_id"`
}

type metaMessage struct {
	From       string           `json:"from"`
	FromUserID string           `json:"from_user_id,omitempty"` // BSUID - Business-Scoped User ID
	ID         string           `json:"id"`
	Timestamp  string           `json:"timestamp"`
	Type       string           `json:"type"`
	Context    *metaContext     `json:"context,omitempty"`
	Text       *metaText        `json:"text,omitempty"`
	Interactive *metaInteractive `json:"interactive,omitempty"`
	Location   *metaLocation    `json:"location,omitempty"`
	Image      *metaImage       `json:"image,omitempty"`
	Document   *metaDocument    `json:"document,omitempty"`
	Audio      *metaAudio       `json:"audio,omitempty"`
	Video      *metaVideo       `json:"video,omitempty"`
	Button     *metaButton      `json:"button,omitempty"`
}

type metaButton struct {
	Text    string `json:"text"`
	Payload string `json:"payload"`
}

type metaContext struct {
	From string `json:"from,omitempty"`
	ID   string `json:"id,omitempty"`
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

type metaImage struct {
	ID       string `json:"id"`
	MimeType string `json:"mime_type,omitempty"`
	Caption  string `json:"caption,omitempty"`
}

type metaDocument struct {
	ID       string `json:"id"`
	MimeType string `json:"mime_type,omitempty"`
	Filename string `json:"filename,omitempty"`
	Caption  string `json:"caption,omitempty"`
}

type metaAudio struct {
	ID       string `json:"id"`
	MimeType string `json:"mime_type,omitempty"`
}

type metaVideo struct {
	ID       string `json:"id"`
	MimeType string `json:"mime_type,omitempty"`
	Caption  string `json:"caption,omitempty"`
}

type incomingMessage struct {
	PhoneNumberID  string
	From           string
	FromUserID     string // BSUID - Business-Scoped User ID
	MessageID      string
	MessageTS      string
	ContextFrom    string
	ContextID      string
	Content        string
	MessageType    string
	SelectedOption string
	FlowPayload    map[string]any
	Location       *metaLocation
	MediaID        string
	MediaMimetype  string
	MediaFilename  string
	// Contact profile fields
	Username    string
	CountryCode string
}

func extractIncomingMessages(evt webhookEvent) []incomingMessage {
	out := make([]incomingMessage, 0)
	for i, e := range evt.Entry {
		log.Printf("[MetaWebhook] DEBUG entry[%d] id=%s changes_count=%d", i, e.ID, len(e.Changes))
		for j, ch := range e.Changes {
			// Log TODOS los fields, no solo "messages"
			log.Printf("[MetaWebhook] DEBUG change[%d][%d] field=%s phone_number_id=%s messages_count=%d statuses_count=%d contacts_count=%d",
				i, j, ch.Field, ch.Value.Metadata.PhoneNumberID, len(ch.Value.Messages), len(ch.Value.Statuses), len(ch.Value.Contacts))
			if ch.Field != "messages" {
				log.Printf("[MetaWebhook] DEBUG skipping field=%s (not messages)", ch.Field)
				continue
			}
			phoneNumberID := ch.Value.Metadata.PhoneNumberID

			// Build contact lookup map by wa_id for efficient lookup
			contactLookup := make(map[string]metaContact)
			for _, contact := range ch.Value.Contacts {
				if contact.WAID != "" {
					contactLookup[contact.WAID] = contact
				}
			}

			for k, msg := range ch.Value.Messages {
				log.Printf("[MetaWebhook] DEBUG message[%d] from=%s type=%s id=%s from_user_id=%s", k, msg.From, msg.Type, msg.ID, msg.FromUserID)
				if msg.From == "" {
					log.Printf("[MetaWebhook] DEBUG message[%d] skipped: empty from", k)
					continue
				}
				content, messageType, selectedOption, flowPayload, location, media := extractMessageData(msg)
				if content == "" && selectedOption == "" && flowPayload == nil && location == nil && media == nil {
					log.Printf("[MetaWebhook] DEBUG message[%d] skipped: no extractable data (type=%s)", k, msg.Type)
					continue
				}

				// Extract contact info if available
				var username, countryCode, contactBSUID string
				if contact, ok := contactLookup[msg.From]; ok {
					username = strings.TrimSpace(contact.Profile.Username)
					countryCode = strings.TrimSpace(contact.Profile.CountryCode)
					contactBSUID = strings.TrimSpace(contact.UserID)
					if username != "" || countryCode != "" || contactBSUID != "" {
						log.Printf("[MetaWebhook] DEBUG message[%d] contact_found wa_id=%s username=%s country_code=%s user_id=%s",
							k, msg.From, username, countryCode, contactBSUID)
					}
				}

				// Determine BSUID: prefer from_user_id from message, fallback to contact's user_id
				fromUserID := strings.TrimSpace(msg.FromUserID)
				if fromUserID == "" && contactBSUID != "" {
					fromUserID = contactBSUID
				}

				// Log BSUID detection
				if fromUserID != "" {
					log.Printf("[MetaWebhook] BSUID detected: from_user_id=%s (from=%s)", fromUserID, msg.From)
				}

				entry := incomingMessage{
					PhoneNumberID:  phoneNumberID,
					From:           msg.From,
					FromUserID:     fromUserID,
					MessageID:      strings.TrimSpace(msg.ID),
					MessageTS:      strings.TrimSpace(msg.Timestamp),
					ContextFrom:    strings.TrimSpace(contextFrom(msg.Context)),
					ContextID:      strings.TrimSpace(contextID(msg.Context)),
					Content:        content,
					MessageType:    messageType,
					SelectedOption: selectedOption,
					FlowPayload:    flowPayload,
					Location:       location,
					Username:       username,
					CountryCode:    countryCode,
				}
				if media != nil {
					entry.MediaID = media.ID
					entry.MediaMimetype = media.MimeType
					entry.MediaFilename = media.Filename
				}
				log.Printf("[MetaWebhook] DEBUG message[%d] extracted: phone_number_id=%s from=%s from_user_id=%s type=%s", k, phoneNumberID, msg.From, fromUserID, messageType)
				out = append(out, entry)
			}
		}
	}
	return out
}

type incomingMedia struct {
	ID       string
	MimeType string
	Filename string
}

func extractMessageData(msg metaMessage) (content, messageType, selectedOption string, flowPayload map[string]any, location *metaLocation, media *incomingMedia) {
	if msg.Type == "text" && msg.Text != nil {
		return msg.Text.Body, "text", "", nil, nil, nil
	}

	// Handle button replies from template messages
	if msg.Type == "button" && msg.Button != nil {
		payload := strings.TrimSpace(msg.Button.Payload)
		text := strings.TrimSpace(msg.Button.Text)
		// Prefer payload over text as it's the developer-defined identifier
		if payload != "" {
			return "", "button_reply", payload, nil, nil, nil
		}
		if text != "" {
			return "", "button_reply", normalizeReplyTitle(text), nil, nil, nil
		}
		return "", "button_reply", "", nil, nil, nil
	}

	if msg.Type == "interactive" && msg.Interactive != nil {
		if msg.Interactive.ButtonReply != nil {
			selected := strings.TrimSpace(msg.Interactive.ButtonReply.ID)
			if selected != "" {
				return "", "interactive_button_reply", selected, nil, nil, nil
			}
			normalizedTitle := normalizeReplyTitle(msg.Interactive.ButtonReply.Title)
			return "", "interactive_button_reply", normalizedTitle, nil, nil, nil
		}
		if msg.Interactive.ListReply != nil {
			return "", "interactive_list_reply", msg.Interactive.ListReply.ID, nil, nil, nil
		}
		if msg.Interactive.NFMReply != nil {
			selected := msg.Interactive.NFMReply.Name
			return "", "interactive_flow_reply", selected, msg.Interactive.NFMReply.ResponseJSON, nil, nil
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
		return contentParts, "location", "", nil, msg.Location, nil
	}

	if msg.Type == "image" && msg.Image != nil && strings.TrimSpace(msg.Image.ID) != "" {
		return strings.TrimSpace(msg.Image.Caption), "image", "", nil, nil, &incomingMedia{
			ID:       strings.TrimSpace(msg.Image.ID),
			MimeType: strings.TrimSpace(msg.Image.MimeType),
		}
	}

	if msg.Type == "document" && msg.Document != nil && strings.TrimSpace(msg.Document.ID) != "" {
		return strings.TrimSpace(msg.Document.Caption), "document", "", nil, nil, &incomingMedia{
			ID:       strings.TrimSpace(msg.Document.ID),
			MimeType: strings.TrimSpace(msg.Document.MimeType),
			Filename: strings.TrimSpace(msg.Document.Filename),
		}
	}

	if msg.Type == "audio" && msg.Audio != nil && strings.TrimSpace(msg.Audio.ID) != "" {
		return "", "audio", "", nil, nil, &incomingMedia{
			ID:       strings.TrimSpace(msg.Audio.ID),
			MimeType: strings.TrimSpace(msg.Audio.MimeType),
		}
	}

	if msg.Type == "video" && msg.Video != nil && strings.TrimSpace(msg.Video.ID) != "" {
		return strings.TrimSpace(msg.Video.Caption), "video", "", nil, nil, &incomingMedia{
			ID:       strings.TrimSpace(msg.Video.ID),
			MimeType: strings.TrimSpace(msg.Video.MimeType),
		}
	}

	if msg.Text != nil && msg.Text.Body != "" {
		return msg.Text.Body, "text", "", nil, nil, nil
	}
	return "", "", "", nil, nil, nil
}

func normalizeReplyTitle(raw string) string {
	return strings.ToLower(strings.TrimSpace(raw))
}

func contextFrom(ctx *metaContext) string {
	if ctx == nil {
		return ""
	}
	return ctx.From
}

func contextID(ctx *metaContext) string {
	if ctx == nil {
		return ""
	}
	return ctx.ID
}
