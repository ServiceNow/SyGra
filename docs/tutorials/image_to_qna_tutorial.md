# Image to QnA Tutorial

This tutorial demonstrates how to build a multimodal Question and Answer (QnA) system for images using the GraSP framework. You’ll learn to extract text from images, generate questions, and provide detailed answers using LLMs.

> **Key Features You’ll Learn**  
> `multimodal LLMs`, `text extraction`, `question generation`, `image processing`, `multi-step reasoning`

---

## Prerequisites

- GraSP framework installed (see [Installation Guide](../installation.md))
- Access to multimodal LLMs (e.g., Qwen VL 72B)
- Basic understanding of image and text data

---

## What You’ll Build

You’ll create a system that:
- **Processes images** and extracts text
- **Generates diverse questions** based on the text
- **Answers questions** with reasoning and evidence
- **Handles multiple images as a document set**

---

## Step 1: Project Structure

```
image_to_qna/
├── graph_config.yaml    # Workflow for image processing, QnA generation
├── task_executor.py     # Custom processors and logic
```

## Step 2: Pipeline Implementation

### Parent Graph (`graph_config.yaml`)

The main pipeline is defined in `image_to_qna/graph_config.yaml`:

- **Data Source**: Loads images and metadata from the `HuggingFaceM4/Docmatix` dataset, applying transformations for image metadata and loop counters.
- **Nodes**:
  - `extract_text`: An LLM node with custom pre- and post-processors. Extracts text from each image.
  - `update_loop_count`: Updates the loop counter for image processing.
  - `generate_questions`: Generates questions from the extracted text.
  - `generate_answers`: Answers each generated question using the document content and question.
- **Edges**: The graph loops over images and questions, processing each in turn.
- **Output Config**: Custom output formatting is handled by the output generator in `task_executor.py`.

**Reference:** [image_to_qna/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/image_to_qna/graph_config.yaml)

### Task Executor (`task_executor.py`)

This file implements custom logic for the pipeline:
- **ImagesMetadata, ImagesPreProcessor, ExtractTextPostProcessor**: Handle image metadata, pre-processing, and text extraction.
- **ImageLoopChecker**: Edge condition for looping through images.
- **Output formatting**: Assembles all image references, extracted text, questions, answers, and reasoning in a single output.

**Reference:** [task_executor.py](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/image_to_qna/task_executor.py)

## Step 3: Output Collection

- Assembles all image references, extracted text, questions, answers, and reasoning in a single output

## Step 4: Running the Pipeline

From your GraSP project root, run:

```bash
python main.py --task path/to/your/image_to_qna
```

Or use the CLI:

```bash
grasp run path/to/your/image_to_qna
```

---

## Example Output

```json
[
    {
        "id": "de850e9019beb83118db75f247a9b17dda378a98abb83c99562593af00a461af",
        "num_images": 1,
        "ocr_texts": ["WISE COUNTY BOARD OF SUPERVISORS..."],
        "num_questions": 3,
        "generated_questions": ["What specific topics...", "Considering the agenda items...", "When and where is the Wise County Board..."]
        // ...
    }
]
```

---

## Try It Yourself

- Use your own images or datasets
- Adjust the prompt for different question types

---

## Next Steps

- Explore [audio to text](audio_to_text_tutorial.md) for multimodal audio processing
- Learn about [structured output](structured_output_tutorial.md) for standardized results
