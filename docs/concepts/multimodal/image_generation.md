# Image Generation and Editing

This module introduces support for multimodal data generation pipelines that produce **image outputs** using AI image generation and editing models. It enables text-to-image generation and image editing tasks, expanding traditional text-only pipelines to support visual content creation.

## Key Features

- Supports **text-to-image** generation from natural language descriptions.
- Supports **image editing** with text instructions (single or multiple images).
- Returns **base64-encoded image data URLs** compatible with standard image formats.
- Compatible with HuggingFace datasets, streaming, and on-disk formats.

## Supported Models

**Currently, we only support the following OpenAI image models:**

- `dall-e-2` - DALL-E 2 for image generation and editing
  - Sizes: 256x256, 512x512, 1024x1024
  - Batch generation: Up to 10 images
  - Single image editing only

- `dall-e-3` - DALL-E 3 for high-quality image generation
  - Sizes: 1024x1024, 1792x1024, 1024x1792
  - Quality: standard or hd
  - Style: vivid or natural
  - Single image per request

- `gpt-image-1` - Latest GPT-Image model with enhanced capabilities
  - Same features as DALL-E 3
  - **Multi-image editing**: Up to 16 images per request
  - Supports PNG, WEBP, JPG formats
  - Maximum file size: 50MB per image

## Input Requirements

### Text-to-Image Generation

For image generation from text:

- **Text prompt**: Natural language description of the desired image
- Maximum length: 
  - DALL-E-2: 1000 characters
  - DALL-E-3: 4000 characters
  - GPT-Image-1: 32000 characters

### Image Editing

For image editing with text instructions:

- **Images**: One or more images can be passed as image_url (refer to [image_to_text.md](./image_to_text.md) to see how input images are handled)
  - DALL-E-2: Single image only (PNG, square, < 4MB)
  - GPT-Image-1: 1-16 images (PNG/WEBP/JPG, < 50MB each)
- **Text prompt**: Instruction describing the desired edits

## How Image Generation Works

### Text-to-Image Flow

1. Text prompt is extracted from the input record.
2. The image model generates image(s) from the prompt.
3. Image(s) are returned as **base64-encoded data URLs** (e.g., `data:image/png;base64,...`).
4. Data URLs are converted to files and saved to disk.
5. Output contains absolute paths to the saved image files.

### Image Editing Flow

1. System detects images in the input (data URLs).
2. If images present → routes to **edit_image** API.
4. Edited images are returned as data URLs and saved to disk.
5. Output contains absolute paths to the saved edited image files.

## Model Configuration

The model configuration must specify `output_type: image` and include image-specific parameters:

### Basic Text-to-Image Configuration

```yaml
dalle3_model:
  model: dalle_3
  output_type: image
  model_type: openai
  parameters:
    size: "1024x1024"
    quality: "hd"
    style: "vivid"
```

### Image Editing Configuration

```yaml
gpt_image_1:
  model: gpt_image_1
  output_type: image
  model_type: azure_openai
  api_version: 2025-03-01-preview
  parameters:
    quality: "medium"
```

## Example 1: Product Image Generation

Generate product images from descriptions:

```yaml
data_config:
  source:
    type: "disk"
    file_path: "data/products.json"

graph_config:
  nodes:
    generate_product_images:
      node_type: llm
      output_keys: product_image
      prompt:
        - user: |
            A professional product photo of {product_name}: {product_description}.
            Studio lighting, white background, high quality, commercial photography.
      model:
        name: dalle3_model
        parameters:
          size: "1024x1024"
          quality: "hd"
          style: "natural"
  
  edges:
    - from: START
      to: generate_product_images
    - from: generate_product_images
      to: END

output_config:
  output_map:
    id:
      from: "id"
    product_name:
      from: "product_name"
    product_image:
      from: "product_image"
```

### Input Data (`data/products.json`)

```json
[
  {
    "id": "1",
    "product_name": "Wireless Headphones",
    "product_description": "Premium over-ear headphones with noise cancellation, matte black finish"
  },
  {
    "id": "2",
    "product_name": "Smart Watch",
    "product_description": "Modern fitness tracker with OLED display, silver aluminum case"
  }
]
```

### Output

```json
[
  {
    "id": "1",
    "product_name": "Wireless Headphones",
    "product_image": "/path/to/multimodal_output/image/1_product_image_0.png"
  },
  {
    "id": "2",
    "product_name": "Smart Watch",
    "product_image": "/path/to/multimodal_output/image/2_product_image_0.png"
  }
]
```

## Example 2: Image Editing (Background Removal)

Edit existing images with text instructions:

```yaml
data_config:
  source:
    type: "disk"
    file_path: "data/photos.json"

graph_config:
  nodes:
    edit_background:
      node_type: llm
      output_keys: edited_image
      prompt:
        - user:
            - type: image_url
              image_url: "{original_image}"
            - type: text
              text: "Remove the background and replace it with a solid white background. Keep the subject unchanged."
      model:
        name: gpt_image_1
        parameters:
          size: "1024x1024"
  
  edges:
    - from: START
      to: edit_background
    - from: edit_background
      to: END

output_config:
  output_map:
    id:
      from: "id"
    original_image:
      from: "original_image"
    edited_image:
      from: "edited_image"
```

### Input Data (`data/photos.json`)

```json
[
  {
    "id": "1",
    "original_image": "data:image/png;base64,iVBORw0KGgo..."
  },
  {
    "id": "2",
    "original_image": "data:image/png;base64,iVBORw0KGgo..."
  }
]
```

### Output

```json
[
  {
    "id": "1",
    "original_image": "data:image/png;base64,iVBORw0KGgo...",
    "edited_image": "/path/to/multimodal_output/image/1_edited_image_0.png"
  },
  {
    "id": "2",
    "original_image": "data:image/png;base64,iVBORw0KGgo...",
    "edited_image": "/path/to/multimodal_output/image/2_edited_image_0.png"
  }
]
```

## Example 3: Multi-Image Editing (GPT-Image-1)

Edit multiple images simultaneously to create a collage:

```yaml
data_config:
  source:
    type: "disk"
    file_path: "data/photo_sets.json"

graph_config:
  nodes:
    create_collage:
      node_type: llm
      output_keys: collage
      prompt:
        - user:
            - type: image_url
              image_url: "{image_1}"
            - type: image_url
              image_url: "{image_2}"
            - type: image_url
              image_url: "{image_3}"
            - type: text
              text: "Arrange these images into a beautiful 3-panel collage with white borders. Maintain image quality."
      model:
        name: gpt_image_1
        parameters:
          quality: "medium"
  
  edges:
    - from: START
      to: create_collage
    - from: create_collage
      to: END

output_config:
  output_map:
    id:
      from: "id"
    collage:
      from: "collage"
```

### Input Data (`data/photo_sets.json`)

```json
[
  {
    "id": "1",
    "image_1": "data:image/png;base64,iVBORw0KGgo...",
    "image_2": "data:image/png;base64,iVBORw0KGgo...",
    "image_3": "data:image/png;base64,iVBORw0KGgo..."
  }
]
```

### Output

```json
[
  {
    "id": "1",
    "collage": "/path/to/multimodal_output/image/1_collage_0.png"
  }
]
```

## Example 4: Batch Image Generation

Generate multiple variations in one request:

```yaml
data_config:
  source:
    type: "disk"
    file_path: "data/concepts.json"

graph_config:
  nodes:
    generate_variations:
      node_type: llm
      output_keys: images
      prompt:
        - user: "{concept_description}"
      model:
        model: dalle_2
        parameters:
          size: "512x512"
          n: 5  # Generate 5 variations
  
  edges:
    - from: START
      to: generate_variations
    - from: generate_variations
      to: END

output_config:
  output_map:
    id:
      from: "id"
    concept:
      from: "concept_description"
    images:
      from: "images"
```

### Input Data (`data/concepts.json`)

```json
[
  {
    "id": "1",
    "concept_description": "A futuristic city skyline at sunset with flying cars"
  }
]
```

### Output

```json
[
  {
    "id": "1",
    "concept": "A futuristic city skyline at sunset with flying cars",
    "images": [
        "/path/to/multimodal_output/image/1_images_0.png",
        "/path/to/multimodal_output/image/1_images_1.png",
        "/path/to/multimodal_output/image/1_images_2.png",
        "/path/to/multimodal_output/image/1_images_3.png",
        "/path/to/multimodal_output/image/1_images_4.png"
      ]
  }
]
```

## Auto-Detection Logic

The system automatically detects the operation type:

1. **Input has images** → Routes to **edit_image()** API (image editing)
2. **Input has no images** → Routes to **create_image()** API (text-to-image)

This means you only need to set `output_type: image` - the system handles the rest!

## Output File Organization

Generated images are saved to:

```
task_dir/
└── multimodal_output/
    └── image/
        ├── {record_id}_{field_name}_0.png
        ├── {record_id}_{field_name}_1.png
        └── ...
```

- `record_id`: ID from input record
- `field_name`: Output field name from prompt
- `index`: Image index (for multiple images)

## Notes

- **Image generation is currently only supported for OpenAI models** (DALL-E-2, DALL-E-3, GPT-Image-1).
- The `output_type` in model configuration must be set to `image` to enable image operations.
- Image files are automatically saved and paths are inserted into the output.
- Multi-image editing requires GPT-Image-1 model; other models support single image only.
- All image models have their own limitations and restrictions; refer to the [OpenAI Image API Documentation](https://platform.openai.com/docs/guides/images) before use.

---

## See Also

- [Text to Speech](./text_to_speech.md) - For audio generation
- [Audio to Text](./audio_to_text.md) - For speech recognition and transcription
- [Image to Text](./image_to_text.md) - For vision-based multimodal pipelines
- [OpenAI Image API Documentation](https://platform.openai.com/docs/guides/images) - Official OpenAI Image API reference
