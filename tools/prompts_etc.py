PROMPTS = {
    "speaker_mapping": {
            "message": """
                We currently had a meeting and used a speech to text service to transcribe the meeting
                (the transcription is attached below).
                The meeting was held in German and the transcription model probably made some mistakes.
                For example, it has problems with correctly transcribing numbers and company names etc.
                Also, we saw, that sometimes adds the word 'zweitausendeins' or something similar to the transcript.
                So please be not confused by this.
                The transcription tool adde speaker labels to the transcript (like Speaker A, Speaker B and so on)
                but did not infer the participants names.
                Please infer which speaker is which participant. The list of participants is:
                {participants}
                Please respond with a JSON object with the following format:
                {example_json}

                Thanks for your help!

                The transcript is:
                {transcript}

                Please respond with the JSON object only.
            """,
            "system": (
                "You are an AI assistant specialized in analyzing meeting transcripts. "
                "You can identify speakers, extract key information, and format the results as structured JSON. "
                "Always respond with only the requested JSON format without additional explanations."
            )
        },
    "infer_agenda": {
            "message": """
                The transcript you find below is the transcript of a meeting. It was automatically 
                transcribed by a speech to text service. The transcription model probably made some 
                mistakes. For example, it has problems with correctly transcribing numbers and company 
                names etc. Also, we saw, that sometimes adds the word 'zweitausendeins' or something 
                similar to the transcript. 
                Also, it sometimes happens that the speaker labels of some parts of the transcript 
                are not aligned well with who actually spoke. So please be not confused by this. 
                Please infer an agenda from the transcript, i.e., an agenda which the meeting could 
                have followed. 
                Please respond with the agenda only and keep it concise and to the point. 
                The transcript is: 
                {transcript} 
                
                The topic of the meeting was: {topic} 
                
                Here are some examples for a good agenda: 
                {agenda_examples} 
            """,
            "system": (
                "You are an AI assistant specialized in analyzing meeting transcripts. "
                "You can extract key information, summarize the content and infer an agenda "
                "based on the content of the transcript. "
                "Always respond with an agenda in bullet points. Make it concise and to the point. "
                "The agenda should be in the same language as the transcript. "
                "Please respond with the agenda only."
            )
        },
    "create_meeting_protocol": {
            "message": """
                The transcript you find below is the transcript of a meeting. It was automatically 
                transcribed by a speech to text service. The transcription model probably made some 
                mistakes. For example, it has problems with correctly transcribing numbers and company 
                names etc. Also, we saw, that sometimes adds the word 'zweitausendeins' or something 
                similar to the transcript. 
                Also we found some parts of the transcript where the speaker labels are not aligned 
                well with who actually spoke. So please be not confused by this. 
                Please create a meeting protocol from the transcript and the agenda. In doing so, 
                make sure to include all important points that were discussed and the decisions that were made. 
                Further, try to infer the opinions of the participants and what was important to them 
                such that I can send it to everyone afterwards and they are satisfied with the outcome. 
                The agenda of the meeting is: 
                {agenda} 
                The transcript is: 
                {transcript} 
                The date of the meeting was: {date} 
                
                Here are some examples for a good meeting protocol: 
                {protocol_examples}
            """,
            "system": (
                "You are an AI assistant specialized in creating meeting protocols. "
                "You can create a meeting protocol from a transcript and an agenda. "
                "Always respond with a meeting protocol in bullet points. "
                "Make it detailed but still to the point. Keep it strictly to what was said in the meeting. "
                "And try to correctly infer the opinions of the participants and what was important to them. "
                "The meeting protocol should be in the same language as the transcript. "
            )
        },
    "create_filename": {
            "message": """
                Please create a filename for the meeting protocol. 
                The date is: 
                {date} 
                The meeting protocol is: 
                {meeting_protocol} 
            """,
            "system": (
                "You are an AI assistant specialized in analyzing meeting protocols. "
                "You can create a descriptive filename for a meeting protocol and a date. "
                "The filename should be in the same language as the meeting protocol. "
                "Always respond with a filename only. The file is supposed to be uploaded to google drive. "
                "The date is: {date} "
                "The meeting protocol is: {meeting_protocol} "
                "Good examples for filenames are: "
                "25.02.25 - Retrospektive und Feedback, Abrunden von Meetingstrukturen und Entscheidungsformen\n"
                "20.01.2025 - Wertebesprechung orange und grün"
            )
        },
    "ensure_markdown": {
            "message": """
                The meeting protocol is: 
                {meeting_protocol} 
                Please make sure that it is formatted in valid markdown. 
            """,
            "system": (
                "You are an AI assistant specialized in formatting arbitrary text to markdown. "
                "You can ensure that a meeting protocol is formatted in valid markdown. "
                "Always respond with a formatted meeting protocol only. Do not change anything in the content of the protocol. "
                "Just ensure that it is valid markdown. "
            )
        }
}

AGENDA_EXAMPLES = [
        (
            "1. Einführung & Zielsetzung (5 Min)\n"
            "- Motivation für das Prozesschart (Moritz)\n"
            "Methodik: Kurze Präsentation\n"

            "2. Struktur & Erklärungen (25 Min)\n"
            "- Überblick über Prozess und Kernelemente\n"
            "- Sammlung offener Fragen\n"
            "Methodik: Strukturierte Durchsprache mit Notizen\n"

            "3. Offene Fragen & Priorisierung (10 Min)\n"
            "- Durchgehen und Priorisieren der Fragen\n"
            "Methodik: Eisenhower-Matrix (Sofort entscheiden/Diskutieren/Delegieren)\n"

            "4. Nächste Schritte (5 Min)\n"
            "- Maßnahmen und Verantwortlichkeiten festlegen\n"
            "Methodik: Klare Aufgabenzuweisung und ggf. Folgetermine"
        ),
        (
            "1. Einführung & Zielsetzung (10 Min)\n"
            "- Ziel des Meetings: Meinungsaustausch zum Prozess, Klärung von Unklarheiten\n"
            "- Agenda-Check: Passt die Agenda zum Ziel?\n"
            "Methodik: Agenda-Vorstellung mit Raum für Anpassungen\n"

            "2. Meinungsaustausch & offene Fragen (15 Min)\n"
            "- Kurzer Rückblick auf letztes Meeting\n"
            "- Identifikation von Sach- und Meinungsfragen\n"
            "Methodik: Offene Diskussionsrunde mit Kategorisierung der Fragen\n"

            "3. Thematische Einordnung (20 Min)\n"
            "- Priorisierung: Was klären wir heute, was später?\n"
            "Methodik: Kategorisierung in \"Heute klären\", \"Folgegespräch\", \"Anderer Kontext\"\n"

            "4. Nächste Schritte & Abschluss (5 Min)\n"
            "- Konkrete Maßnahmen und Verantwortlichkeiten\n"
            "- Festlegung weiterer Termine (falls nötig)\n"
        )
    ]
