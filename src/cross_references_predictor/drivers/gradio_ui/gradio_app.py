import gradio as gr
import requests
import json
from typing import Dict, Any, Tuple
import time

SERVICE_URL = "http://localhost:5070"

ENTITY_COLORS = {
    "PERSON": "#4A90E2",
    "ORGANIZATION": "#E74C3C",
    "LOCATION": "#2ECC71",
    "DATE": "#F39C12",
    "LAW": "#9B59B6",
    "DOCUMENT_CODE": "#1ABC9C",
    "REFERENCE": "#D35400",
}


def format_entity_display(entity: Dict[str, Any]) -> str:
    entity_type = entity.get("type", "UNKNOWN")
    text = entity.get("text", "")
    relevance = entity.get("relevance_percentage", 0)
    color = ENTITY_COLORS.get(entity_type, "#95A5A6")
    label = f"{text} ({entity_type}) [{relevance}%]" if relevance else f"{text} ({entity_type})"
    return f'<span style="background-color: {color}; padding: 2px 6px; border-radius: 3px; color: white; margin: 2px; display: inline-block;">{label}</span>'


def format_entities_html(entities: list) -> str:
    if not entities:
        return "<p>No entities found.</p>"
    html = "<div style='line-height: 2.5;'>"
    entities_by_type = {}
    for entity in entities:
        entity_type = entity.get("type", "UNKNOWN")
        if entity_type not in entities_by_type:
            entities_by_type[entity_type] = []
        entities_by_type[entity_type].append(entity)
    for entity_type, type_entities in entities_by_type.items():
        color = ENTITY_COLORS.get(entity_type, "#95A5A6")
        html += f'<h4 style="color: {color}; margin-top: 15px;">{entity_type} ({len(type_entities)})</h4>'
        html += '<div style="margin-bottom: 10px;">'
        for entity in type_entities:
            html += format_entity_display(entity)
        html += "</div>"
    html += "</div>"
    return html


def create_legend() -> str:
    legend_html = "<div style='padding: 10px; background-color: #f5f5f5; border-radius: 5px; margin-bottom: 10px;'>"
    legend_html += "<h4 style='margin-top: 0;'>Entity Types Legend:</h4>"
    legend_html += "<div style='display: flex; flex-wrap: wrap; gap: 10px;'>"
    entity_labels = {
        "PERSON": "Person (PER)",
        "ORGANIZATION": "Organization (ORG)",
        "LOCATION": "Location (LOC)",
        "DATE": "Date (DAT)",
        "LAW": "Law (LAW)",
        "DOCUMENT_CODE": "Document Code (DOC)",
        "REFERENCE": "Reference (REF)",
    }
    for entity_type, label in entity_labels.items():
        color = ENTITY_COLORS.get(entity_type, "#95A5A6")
        legend_html += f'<span style="background-color: {color}; padding: 5px 10px; border-radius: 3px; color: white; font-weight: bold;">{label}</span>'
    legend_html += "</div></div>"
    return legend_html


def extract_entities_from_text(
    text: str, language: str = "en", progress: gr.Progress = gr.Progress()
) -> Tuple[str, str, str]:
    progress(0, desc="Starting text extraction...")
    if not text.strip():
        return "<p style='color: red;'>Please enter some text.</p>", "", ""
    try:
        progress(0.3, desc="Contacting service...")
        response = requests.post(f"{SERVICE_URL}/", data={"text": text, "language": language}, timeout=300)
        if response.status_code != 200:
            return f"<p style='color: red;'>Error: Service returned status code {response.status_code}</p>", "", ""
        progress(0.7, desc="Processing results...")
        result = response.json()
        references = result.get("references", [])
        entities_html = format_entities_html(references)
        json_response = json.dumps(result, indent=2)
        progress(1.0, desc="Done!")
        return entities_html, json_response, ""
    except requests.exceptions.ConnectionError:
        return (
            "<p style='color: red;'>Error: Cannot connect to Cross-References Predictor service. Make sure it's running.</p>",
            "",
            "",
        )
    except Exception as e:
        return f"<p style='color: red;'>Error: {str(e)}</p>", "", ""


def extract_entities_from_pdf(
    pdf_file, language: str = "en", fast: bool = False, progress: gr.Progress = gr.Progress()
) -> Tuple[str, str, str]:
    progress(0, desc="Starting PDF extraction...")
    if pdf_file is None:
        return "<p style='color: red;'>Please upload a PDF file.</p>", "", ""
    try:
        progress(0.2, desc="Reading PDF file...")
        with open(pdf_file, "rb") as f:
            pdf_content = f.read()
        files = {"file": ("document.pdf", pdf_content, "application/pdf")}
        data = {"language": language, "fast": fast}
        progress(0.5, desc="Contacting service...")
        entities_response = requests.post(f"{SERVICE_URL}/", files=files, data=data, timeout=300)
        if entities_response.status_code == 200:
            progress(0.8, desc="Processing results...")
            result = entities_response.json()
            references = result.get("references", [])
            entities_html = format_entities_html(references)
            json_response = json.dumps(result, indent=2)
            progress(1.0, desc="Done!")
            return entities_html, json_response, ""
        else:
            return f"<p style='color: red;'>Error: Service returned status code {entities_response.status_code}</p>", "", ""
    except requests.exceptions.ConnectionError:
        return (
            "<p style='color: red;'>Error: Cannot connect to Cross-References Predictor service. Make sure it's running.</p>",
            "",
            "",
        )
    except Exception as e:
        return f"<p style='color: red;'>Error: {str(e)}</p>", "", ""


def wait_for_backend(max_retries: int = 60, retry_interval: int = 2) -> bool:
    print("\n" + "=" * 80, flush=True)
    print(" Waiting for Cross-References Predictor service to be ready...".center(80), flush=True)
    print("=" * 80 + "\n", flush=True)
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(f"{SERVICE_URL}/", timeout=5)
            if response.status_code == 200:
                print("=" * 80, flush=True)
                print(" CROSS-REFERENCES PREDICTOR UI IS READY!".center(80), flush=True)
                print("=" * 80, flush=True)
                print("", flush=True)
                print(" Access the UI at:", flush=True)
                print("   -> http://localhost:7860", flush=True)
                print("", flush=True)
                return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(retry_interval)
        except Exception as e:
            print(f"   Unexpected error while checking backend: {str(e)}", flush=True)
            time.sleep(retry_interval)
    print("\n" + "=" * 80, flush=True)
    print(" Backend service did not become ready in time!".center(80), flush=True)
    print("=" * 80 + "\n", flush=True)
    return False


with gr.Blocks(title="Cross-References Predictor", theme=gr.themes.Soft()) as app:
    gr.Markdown("# Cross-References Predictor")
    gr.Markdown("Detect named entities and cross-references in your documents.")
    gr.HTML(create_legend())

    processing_status = gr.HTML("", elem_id="processing-status")

    with gr.Tabs():
        with gr.Tab("Text Extraction"):
            gr.Markdown("### Extract entities and cross-references from text")
            with gr.Row():
                with gr.Column(scale=2):
                    text_input = gr.Textbox(
                        label="Input Text",
                        placeholder="Enter text here... (e.g., 'John Smith works at Microsoft in Seattle since January 2020.')",
                        lines=10,
                    )
                    with gr.Row():
                        language_text = gr.Dropdown(
                            choices=["en", "es", "de", "fr"],
                            value="en",
                            label="Language",
                            info="Select the language of your text",
                        )
                        extract_text_btn = gr.Button("Extract Entities", variant="primary")

                with gr.Column(scale=2):
                    entities_output = gr.HTML(label="Extracted Entities")

            with gr.Accordion("View JSON Response", open=False):
                json_output_text = gr.Code(label="JSON Response", language="json", lines=15)

            gr.Examples(
                examples=[
                    [
                        "John Smith works at Microsoft in Seattle since January 2020. He reports to the CEO under Article 15 of the company bylaws."
                    ],
                    ["The United Nations held a meeting in Geneva on March 15, 2024, discussing international law reforms."],
                    ["Dr. Sarah Johnson from Harvard University published research in Nature magazine last week."],
                ],
                inputs=text_input,
                label="Example Texts",
            )

            def set_text_status() -> str:
                return '<p style="color: #555;">⏳ Processing... Please wait.</p>'

            extract_text_btn.click(
                fn=set_text_status,
                outputs=[processing_status],
            ).then(
                fn=extract_entities_from_text,
                inputs=[text_input, language_text],
                outputs=[entities_output, json_output_text, processing_status],
            )

        with gr.Tab("PDF Extraction"):
            gr.Markdown("### Extract entities and cross-references from PDF")
            with gr.Row():
                with gr.Column(scale=1):
                    pdf_input = gr.File(label="Upload PDF", file_types=[".pdf"], type="filepath")
                    with gr.Row():
                        language_pdf = gr.Dropdown(
                            choices=["en", "es", "de", "fr"],
                            value="en",
                            label="Language",
                            info="Select the language of your PDF",
                        )
                        fast_mode = gr.Checkbox(
                            label="Fast Mode", value=False, info="Enable for faster processing (less accurate segmentation)"
                        )
                    extract_pdf_btn = gr.Button("Extract Entities", variant="primary")

                with gr.Column(scale=2):
                    with gr.Accordion("Extracted Entities", open=True):
                        entities_output_pdf = gr.HTML(label="Entities")

            with gr.Accordion("View JSON Response", open=False):
                json_output_pdf = gr.Code(label="JSON Response", language="json", lines=15)

            def set_pdf_status() -> str:
                return '<p style="color: #555;">⏳ Processing PDF... Please wait.</p>'

            extract_pdf_btn.click(
                fn=set_pdf_status,
                outputs=[processing_status],
            ).then(
                fn=extract_entities_from_pdf,
                inputs=[pdf_input, language_pdf, fast_mode],
                outputs=[entities_output_pdf, json_output_pdf, processing_status],
            )

    gr.Markdown("---")


if __name__ == "__main__":
    if not wait_for_backend():
        print("Failed to connect to backend service. Exiting...", flush=True)
        exit(1)
    app.queue()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False, quiet=True)
