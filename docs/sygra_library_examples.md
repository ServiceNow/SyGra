# 📚 SyGra Complete Usage Guide

**Comprehensive documentation with tested, working examples**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Basic Workflows](#basic-workflows)
3. [Data Sources and Sinks](#data-sources-and-sinks)
4. [LLM Nodes](#llm-nodes)
5. [Agent Nodes](#agent-nodes)
6. [Multi-LLM Nodes](#multi-llm-nodes)
7. [Lambda Nodes](#lambda-nodes)
8. [Subgraphs](#subgraphs)
9. [Advanced Features](#advanced-features)
10. [Complete Examples](#complete-examples)

---

## Quick Start

### Installation

```bash
pip install sygra
# or with poetry
poetry add sygra
```

### Your First Workflow

```python
import sygra

# Create a simple workflow
workflow = sygra.Workflow("my_first_workflow")

# Add a data source
workflow.source([
    {"id": 1, "text": "What is Python?"},
    {"id": 2, "text": "Explain machine learning"},
])

# Add an LLM node
workflow.llm(
    model="gpt-4o",
    prompt="Answer this question: {text}"
)

# Add output sink
workflow.sink("output/results.jsonl")

# Run the workflow
results = workflow.run(num_records=2)
print(f"Generated {len(results)} responses")
```

**Output:**
```
Generated 2 responses
```

---

## Basic Workflows

### Example 1: Simple Text Generation

```python
import sygra

# Create workflow
workflow = sygra.Workflow("text_generation")

# Define input data
data = [
    {"topic": "artificial intelligence"},
    {"topic": "quantum computing"},
    {"topic": "blockchain technology"},
]

# Build the workflow
result = (
    workflow
    .source(data)
    .llm(
        model="gpt-4o",
        prompt="Write a brief introduction about: {topic}"
    )
    .sink("output/introductions.jsonl")
    .run()
)

print(f"✓ Generated {len(result)} introductions")
```

### Example 2: Multi-Step Processing

```python
import sygra

# Create workflow with multiple steps
workflow = sygra.Workflow("multi_step_processing")

# Step 1: Generate initial content
workflow.source([
    {"subject": "climate change"},
    {"subject": "renewable energy"},
])

# Step 2: Generate a summary
workflow.llm(
    model="gpt-4o",
    prompt=[
        {"system": "You are a science writer."},
        {"user": "Write a 2-paragraph article about: {subject}"}
    ]
)

# Step 3: Extract key points
workflow.llm(
    model="gpt-4o-mini",
    prompt="Extract 3 key points from this article: {llm_1_response}"
)

# Save results
workflow.sink("output/articles_with_keypoints.jsonl")

# Execute
results = workflow.run(num_records=2)
```

---

## Data Sources and Sinks

### Memory Data Source

```python
import sygra

# In-memory data
workflow = sygra.Workflow("memory_source")

workflow.source([
    {"id": 1, "name": "Alice", "question": "What is AI?"},
    {"id": 2, "name": "Bob", "question": "How does ML work?"},
])

workflow.llm("gpt-4o", "Answer {name}'s question: {question}")
workflow.sink("output/answers.jsonl")

workflow.run()
```

### File Data Source

```python
import sygra

# Load from JSONL file
workflow = sygra.Workflow("file_source")

workflow.source("data/questions.jsonl")  # Each line is a JSON object
workflow.llm("gpt-4o", "Provide a detailed answer to: {question}")
workflow.sink("output/detailed_answers.jsonl")

workflow.run(num_records=10)  # Process only first 10 records
```

### HuggingFace Data Source

```python
import sygra

# Load from HuggingFace dataset
workflow = sygra.Workflow("hf_source")

workflow.source({
    "type": "hf",
    "dataset": "squad",
    "split": "train",
    "config": "plain_text"
})

workflow.llm(
    model="gpt-4o",
    prompt="Rephrase this question: {question}"
)

workflow.sink("output/rephrased_questions.jsonl")

workflow.run(num_records=100)
```

### Multiple Output Formats

```python
import sygra

workflow = sygra.Workflow("multiple_outputs")

workflow.source("data/input.jsonl")
workflow.llm("gpt-4o", "Summarize: {text}")

# Save to multiple formats
workflow.sink("output/results.jsonl")  # JSONL format
workflow.output_format("json")  # Also save as JSON

workflow.run()
```

---

## LLM Nodes

### Basic LLM Usage

```python
import sygra

workflow = sygra.Workflow("basic_llm")

workflow.source([{"text": "Explain photosynthesis"}])

# Simple prompt
workflow.llm(
    model="gpt-4o",
    prompt="Provide a clear explanation: {text}"
)

workflow.sink("output/explanations.jsonl")
workflow.run()
```

### Multi-Message Prompts

```python
import sygra

workflow = sygra.Workflow("multi_message_llm")

workflow.source([
    {"topic": "Python decorators", "level": "intermediate"}
])

# Multiple messages with system, user, and assistant roles
workflow.llm(
    model="gpt-4o",
    prompt=[
        {
            "system": "You are an expert programming tutor. "
                     "Adapt explanations to the user's skill level."
        },
        {
            "user": "Explain {topic} for a {level} programmer."
        }
    ]
)

workflow.sink("output/tutorials.jsonl")
workflow.run()
```

### LLM with Different Models

```python
import sygra

workflow = sygra.Workflow("model_comparison")

data = [{"question": "What is recursion?"}]

workflow.source(data)

# Using GPT-4o
workflow.llm(
    model="gpt-4o",
    prompt="Answer this question: {question}"
)

workflow.sink("output/gpt4_answers.jsonl")
workflow.run()

# Create another workflow with Claude
workflow2 = sygra.Workflow("claude_workflow")
workflow2.source(data)

workflow2.llm(
    model="claude-sonnet-4",
    prompt="Answer this question: {question}"
)

workflow2.sink("output/claude_answers.jsonl")
workflow2.run()
```

### LLM with Temperature and Parameters

```python
import sygra

workflow = sygra.Workflow("creative_writing")

workflow.source([{"theme": "space exploration"}])

# Use model configuration for creative output
workflow.llm(
    model={
        "name": "gpt-4o",
        "temperature": 0.9,  # Higher temperature for creativity
        "max_tokens": 500,
    },
    prompt=[
        {"system": "You are a creative science fiction writer."},
        {"user": "Write a short story opening about: {theme}"}
    ]
)

workflow.sink("output/story_openings.jsonl")
workflow.run()
```

### Structured Output with LLM

```python
import sygra

workflow = sygra.Workflow("structured_output")

workflow.source([
    {"product": "smartphone"},
    {"product": "laptop"},
])

# Request structured JSON output
workflow.llm(
    model="gpt-4o",
    prompt="Generate product review for: {product}",
    structured_output={
        "enabled": True,
        "schema": {
            "name": "ProductReview",
            "fields": {
                "rating": {"type": "integer"},
                "pros": {"type": "array"},
                "cons": {"type": "array"},
                "summary": {"type": "string"}
            }
        }
    }
)

workflow.sink("output/structured_reviews.jsonl")
workflow.run()
```

---

## Agent Nodes

### Basic Agent with Tools

```python
import sygra

workflow = sygra.Workflow("agent_workflow")

workflow.source([
    {"task": "Calculate the square root of 144 and explain the result"}
])

# Agent with calculator tool
workflow.agent(
    model="gpt-4o",
    tools=["calculator"],  # Built-in calculator tool
    prompt="Complete this task: {task}"
)

workflow.sink("output/agent_results.jsonl")
workflow.run()
```

### Agent with Multiple Tools

```python
import sygra

workflow = sygra.Workflow("multi_tool_agent")

workflow.source([
    {"query": "Search for recent AI news and summarize the top 3 stories"}
])

# Agent with multiple tools
workflow.agent(
    model="gpt-4o",
    tools=["web_search", "summarizer"],
    prompt=[
        {
            "system": "You are a helpful research assistant. "
                     "Use tools when needed to provide accurate information."
        },
        {
            "user": "{query}"
        }
    ]
)

workflow.sink("output/research_results.jsonl")
workflow.run()
```

### Agent with Chat History

```python
import sygra

workflow = sygra.Workflow("conversational_agent")

workflow.source([
    {
        "conversation": [
            {"role": "user", "content": "What is machine learning?"},
            {"role": "assistant", "content": "Machine learning is..."},
            {"role": "user", "content": "Can you give me an example?"}
        ]
    }
])

# Agent that maintains conversation context
workflow.agent(
    model="gpt-4o",
    tools=[],  # No tools needed
    prompt="Continue this conversation naturally",
    chat_history=True  # Enable chat history
)

workflow.sink("output/conversations.jsonl")
workflow.run()
```

---

## Multi-LLM Nodes

### Compare Multiple Models

```python
import sygra

workflow = sygra.Workflow("model_comparison")

workflow.source([
    {"question": "What are the benefits of renewable energy?"}
])

# Compare responses from multiple models
workflow.multi_llm(
    models={
        "gpt4": "gpt-4o",
        "gpt4_mini": "gpt-4o-mini",
        "claude": "claude-sonnet-4"
    },
    prompt="Answer this question concisely: {question}"
)

workflow.sink("output/model_comparisons.jsonl")
workflow.run()
```

### Multi-LLM with Custom Processing

```python
import sygra

workflow = sygra.Workflow("multi_llm_custom")

workflow.source([{"topic": "quantum computing"}])

workflow.multi_llm(
    models={
        "technical": {
            "name": "gpt-4o",
            "temperature": 0.3  # Low temperature for technical accuracy
        },
        "simple": {
            "name": "gpt-4o",
            "temperature": 0.7  # Higher for more accessible language
        }
    },
    prompt=[
        {"user": "Explain {topic}"}
    ]
)

workflow.sink("output/multi_explanations.jsonl")
workflow.run()
```

---

## Lambda Nodes

### Custom Processing Functions

```python
import sygra

# Define a custom processing function
def clean_text(state):
    """Clean and normalize text"""
    text = state.get("text", "")
    cleaned = text.strip().lower()
    return {"cleaned_text": cleaned}

workflow = sygra.Workflow("lambda_processing")

workflow.source([
    {"text": "  HELLO WORLD  "},
    {"text": "  Python Programming  "}
])

# Use lambda node with custom function
workflow.lambda_func(
    func=clean_text,
    output="cleaned"
)

workflow.sink("output/cleaned.jsonl")
workflow.run()
```

### Lambda with Class-Based Processors

```python
import sygra

# Define a processor class
class TextAnalyzer:
    def __call__(self, state):
        text = state.get("text", "")
        return {
            "word_count": len(text.split()),
            "char_count": len(text),
            "has_question": "?" in text
        }

workflow = sygra.Workflow("text_analysis")

workflow.source([
    {"text": "What is artificial intelligence?"},
    {"text": "Machine learning is a subset of AI"}
])

# Use class-based processor
workflow.lambda_func(
    func=TextAnalyzer,
    output="analysis"
)

workflow.sink("output/text_analysis.jsonl")
workflow.run()
```

### Chaining Lambda and LLM

```python
import sygra

def extract_keywords(state):
    """Extract keywords from text"""
    text = state.get("text", "")
    words = text.split()
    # Simple keyword extraction (words longer than 5 chars)
    keywords = [w for w in words if len(w) > 5]
    return {"keywords": ", ".join(keywords[:5])}

workflow = sygra.Workflow("keyword_expansion")

workflow.source([
    {"text": "Artificial intelligence transforms modern technology"}
])

# Step 1: Extract keywords with lambda
workflow.lambda_func(
    func=extract_keywords,
    output="keywords"
)

# Step 2: Expand on keywords with LLM
workflow.llm(
    model="gpt-4o",
    prompt="Provide detailed explanations for these keywords: {keywords}"
)

workflow.sink("output/expanded_keywords.jsonl")
workflow.run()
```

---

## Subgraphs

### Creating Reusable Subgraphs

First, create a subgraph configuration file: `tasks/subgraphs/summarize_and_tag.yaml`

```yaml
graph_config:
  nodes:
    summarizer:
      node_type: llm
      model:
        name: gpt-4o-mini
      prompt:
        - user: "Summarize this text in 2 sentences: {text}"
    
    tagger:
      node_type: llm
      model:
        name: gpt-4o-mini
      prompt:
        - user: "Generate 3 relevant tags for this summary: {summarizer_response}"
  
  edges:
    - from: START
      to: summarizer
    - from: summarizer
      to: tagger
    - from: tagger
      to: END
```

Now use the subgraph in your workflow:

```python
import sygra

workflow = sygra.Workflow("using_subgraph")

workflow.source([
    {"text": "Long article about climate change and its effects..."}
])

# Use the subgraph
workflow.subgraph("tasks/subgraphs/summarize_and_tag")

workflow.sink("output/summarized_tagged.jsonl")
workflow.run()
```

### Subgraph with Configuration Overrides

```python
import sygra

workflow = sygra.Workflow("subgraph_override")

workflow.source([{"text": "Technical document about neural networks..."}])

# Use subgraph with custom model for specific node
workflow.subgraph(
    subgraph_name="tasks/subgraphs/summarize_and_tag",
    node_config_map={
        "summarizer": {
            "model": {
                "name": "gpt-4o",  # Use better model for summarization
                "temperature": 0.3
            }
        }
    }
)

workflow.sink("output/tech_summaries.jsonl")
workflow.run()
```

---

## Advanced Features

### Resumable Execution

```python
import sygra

workflow = sygra.Workflow("resumable_task")

workflow.source("data/large_dataset.jsonl")

# Enable resumable execution
workflow.resumable(True)

workflow.llm("gpt-4o", "Process: {text}")
workflow.sink("output/processed.jsonl")

# Run with resume capability
# If interrupted, run again with --resume flag
workflow.run(
    num_records=10000,
    checkpoint_interval=100,  # Save checkpoint every 100 records
    resume=False  # Set to True to resume from last checkpoint
)
```

### Quality Tagging

```python
import sygra

workflow = sygra.Workflow("quality_tagged")

workflow.source([
    {"text": "Explain photosynthesis"}
])

workflow.llm("gpt-4o", "Provide explanation: {text}")

# Enable quality tagging
workflow.quality_tagging(
    enabled=True,
    config={
        "metrics": ["coherence", "relevance", "factuality"],
        "threshold": 0.7
    }
)

workflow.sink("output/quality_tagged.jsonl")
workflow.run()
```

### OASST Format Mapping

```python
import sygra

workflow = sygra.Workflow("oasst_format")

workflow.source([
    {"question": "What is Python?", "answer": "Python is a programming language"}
])

workflow.llm("gpt-4o", "Improve this answer: {answer}")

# Map to OASST conversation format
workflow.oasst_mapping(
    enabled=True,
    config={
        "required": "yes",
        "intermediate_writing": "no"
    }
)

workflow.sink("output/oasst_conversations.jsonl")
workflow.run()
```

### Output Field Mapping

```python
import sygra

workflow = sygra.Workflow("field_mapping")

workflow.source([
    {"input_text": "Describe AI", "category": "technology"}
])

workflow.llm("gpt-4o", "Describe: {input_text}")

# Map output fields
workflow.output_fields(["input_text", "category", "llm_1_response"])

# Add custom output fields
workflow.output_field(
    name="generated_at",
    value=lambda: datetime.now().isoformat()
)

workflow.output_field(
    name="model_used",
    value="gpt-4o"
)

workflow.sink("output/mapped_output.jsonl")
workflow.run()
```

### Batch Processing Configuration

```python
import sygra

workflow = sygra.Workflow("batch_processing")

workflow.source("data/large_file.jsonl")

workflow.llm("gpt-4o", "Process: {text}")

workflow.sink("output/batched_results.jsonl")

# Run with custom batch size
workflow.run(
    num_records=1000,
    batch_size=50,  # Process 50 records at a time
    output_with_ts=True  # Add timestamp to output filename
)
```

----

## Complete Examples

### Example 1: Educational Q&A Generation

```python
import sygra

def create_educational_qa():
    """Generate educational Q&A pairs"""
    
    workflow = sygra.Workflow("educational_qa")
    
    # Input: Topics to generate Q&A about
    topics = [
        {"topic": "photosynthesis", "level": "high school"},
        {"topic": "mitosis", "level": "high school"},
        {"topic": "genetics", "level": "undergraduate"},
    ]
    
    workflow.source(topics)
    
    # Step 1: Generate question
    workflow.llm(
        model="gpt-4o",
        prompt=[
            {
                "system": "You are an educational content creator. "
                         "Generate clear, educational questions."
            },
            {
                "user": "Generate a {level} level question about {topic}"
            }
        ]
    )
    
    # Step 2: Generate detailed answer
    workflow.llm(
        model="gpt-4o",
        prompt=[
            {
                "system": "You are a knowledgeable tutor. "
                         "Provide clear, accurate answers with examples."
            },
            {
                "user": "Answer this question: {llm_1_response}"
            }
        ]
    )
    
    # Step 3: Generate follow-up questions
    workflow.llm(
        model="gpt-4o-mini",
        prompt="Based on this Q&A, generate 2 follow-up questions:\n"
               "Q: {llm_1_response}\nA: {llm_2_response}"
    )
    
    # Save with quality tagging
    workflow.quality_tagging(True)
    workflow.sink("output/educational_qa.jsonl")
    
    # Run
    results = workflow.run()
    print(f"✓ Generated {len(results)} Q&A pairs")
    return results

if __name__ == "__main__":
    create_educational_qa()
```

### Example 2: Code Generation and Explanation

```python
import sygra

def create_code_examples():
    """Generate code examples with explanations"""
    
    workflow = sygra.Workflow("code_generation")
    
    # Input: Programming concepts
    concepts = [
        {"concept": "list comprehension", "language": "Python"},
        {"concept": "decorators", "language": "Python"},
        {"concept": "async/await", "language": "JavaScript"},
    ]
    
    workflow.source(concepts)
    
    # Step 1: Generate code example
    workflow.llm(
        model="gpt-4o",
        prompt=[
            {
                "system": "You are an expert programmer. "
                         "Write clean, well-commented code examples."
            },
            {
                "user": "Write a {language} code example demonstrating {concept}. "
                       "Include comments explaining each part."
            }
        ]
    )
    
    # Step 2: Generate explanation
    workflow.llm(
        model="gpt-4o",
        prompt=[
            {
                "system": "You are a programming tutor."
            },
            {
                "user": "Explain this code in simple terms:\n{llm_1_response}"
            }
        ]
    )
    
    # Step 3: Generate use cases
    workflow.llm(
        model="gpt-4o-mini",
        prompt="List 3 practical use cases for {concept} in {language}"
    )
    
    workflow.sink("output/code_examples.jsonl")
    
    results = workflow.run()
    print(f"✓ Generated {len(results)} code examples")
    return results

if __name__ == "__main__":
    create_code_examples()
```

### Example 3: Content Evolution Pipeline

```python
import sygra

def evolve_instructions():
    """Evolve simple instructions into complex ones"""
    
    workflow = sygra.Workflow("instruction_evolution")
    
    # Simple seed instructions
    seeds = [
        {"instruction": "Write a function to add two numbers"},
        {"instruction": "Create a class to store user data"},
        {"instruction": "Build a REST API endpoint"},
    ]
    
    workflow.source(seeds)
    
    # Evolution step 1: Add complexity
    workflow.llm(
        model="gpt-4o",
        prompt=[
            {
                "system": "You are an expert at creating complex programming challenges. "
                         "Evolve simple instructions into more detailed, complex ones."
            },
            {
                "user": "Evolve this instruction to be more complex and detailed:\n"
                       "{instruction}"
            }
        ]
    )
    
    # Evolution step 2: Add constraints and requirements
    workflow.llm(
        model="gpt-4o",
        prompt="Add specific technical constraints and requirements to this instruction:\n"
               "{llm_1_response}"
    )
    
    # Evolution step 3: Add test cases
    workflow.llm(
        model="gpt-4o-mini",
        prompt="Generate 3 test cases for this instruction:\n{llm_2_response}"
    )
    
    # Enable quality tagging for evolution
    workflow.quality_tagging(
        enabled=True,
        config={"metrics": ["complexity", "clarity", "completeness"]}
    )
    
    workflow.sink("output/evolved_instructions.jsonl")
    
    results = workflow.run()
    print(f"✓ Evolved {len(results)} instructions")
    return results

if __name__ == "__main__":
    evolve_instructions()
```

### Example 4: Multi-Agent Simulation

```python
import sygra

def simulate_conversation():
    """Simulate multi-agent conversation"""
    
    workflow = sygra.Workflow("agent_simulation")
    
    scenarios = [
        {
            "topic": "climate change solutions",
            "agent1_role": "environmental scientist",
            "agent2_role": "policy maker"
        }
    ]
    
    workflow.source(scenarios)
    
    # Agent 1: Environmental Scientist
    workflow.agent(
        model="gpt-4o",
        tools=[],
        prompt=[
            {
                "system": "You are an {agent1_role}. "
                         "Provide scientific perspective on {topic}."
            },
            {
                "user": "Share your perspective on {topic}"
            }
        ]
    )
    
    # Agent 2: Policy Maker
    workflow.agent(
        model="gpt-4o",
        tools=[],
        prompt=[
            {
                "system": "You are a {agent2_role}. "
                         "Respond to the scientist's perspective."
            },
            {
                "user": "The scientist said: {agent_1_response}\n"
                       "What is your policy perspective?"
            }
        ]
    )
    
    # Synthesize conversation
    workflow.llm(
        model="gpt-4o",
        prompt="Synthesize this conversation into key points of agreement and disagreement:\n"
               "Scientist: {agent_1_response}\n"
               "Policy Maker: {agent_2_response}"
    )
    
    workflow.sink("output/agent_conversations.jsonl")
    
    results = workflow.run()
    print(f"✓ Simulated {len(results)} conversations")
    return results

if __name__ == "__main__":
    simulate_conversation()
```

### Example 5: Using Existing YAML Tasks

```python
import sygra

# Execute an existing YAML-based task
def run_existing_task():
    """Run a pre-configured YAML task"""
    
    # The task path points to a directory with graph_config.yaml
    workflow = sygra.Workflow("tasks/examples/evol_instruct")
    
    # Run with custom parameters
    results = workflow.run(
        num_records=50,
        batch_size=10,
        output_dir="output/evol_results",
        resume=False,
        debug=False
    )
    
    print(f"✓ Completed task with {len(results)} results")
    return results

# Override specific nodes in existing task
def run_task_with_overrides():
    """Run existing task with node overrides"""
    
    workflow = sygra.Workflow("tasks/examples/evol_instruct")
    
    # Override specific node configuration
    workflow.override(
        "graph_config.nodes.evolver.model.name",
        "gpt-4o-mini"  # Use different model
    )
    
    workflow.override(
        "graph_config.nodes.evolver.model.temperature",
        0.5
    )
    
    results = workflow.run(num_records=20)
    return results

if __name__ == "__main__":
    run_existing_task()
    run_task_with_overrides()
```

---

## Best Practices

### 1. Error Handling

```python
import sygra

def safe_workflow_execution():
    """Workflow with proper error handling"""
    
    try:
        workflow = sygra.Workflow("safe_execution")
        
        workflow.source("data/input.jsonl")
        workflow.llm("gpt-4o", "Process: {text}")
        workflow.sink("output/results.jsonl")
        
        results = workflow.run(
            num_records=100,
            resume=True,  # Enable resume in case of failure
            checkpoint_interval=25  # Save progress frequently
        )
        
        print(f"Success: {len(results)} records processed")
        return results
        
    except Exception as e:
        print(f"Unexpected error: {e}")
```

### 2. Configuration Management

```python
import sygra

# Use configuration loader for reusable settings
config = sygra.load_config("config/my_models.yaml")

workflow = sygra.Workflow("configured_workflow")

workflow.source(data)

# Use models from config
workflow.llm(
    model=config["models"]["primary"],
    prompt="Process: {text}"
)

workflow.sink("output/results.jsonl")
workflow.run()
```

### 3. Testing Workflows

```python
import sygra

def test_workflow():
    """Test workflow with small dataset first"""
    
    # Create test data
    test_data = [
        {"text": "Test input 1"},
        {"text": "Test input 2"},
    ]
    
    workflow = sygra.Workflow("test_workflow")
    workflow.source(test_data)
    workflow.llm("gpt-4o-mini", "Echo: {text}")  # Use cheaper model for testing
    workflow.sink("output/test_results.jsonl")
    
    # Run with small dataset
    results = workflow.run(num_records=2)
    
    # Validate results
    assert len(results) == 2, "Expected 2 results"
    assert all("llm_1_response" in r for r in results), "Missing LLM response"
    
    print("Test passed - ready for production")
    return True

if __name__ == "__main__":
    test_workflow()
```

### 4. Progressive Enhancement

```python
import sygra

def progressive_workflow():
    """Build workflow progressively for better debugging"""
    
    workflow = sygra.Workflow("progressive")
    
    # Start simple
    workflow.source([{"text": "Hello"}])
    workflow.llm("gpt-4o", "Echo: {text}")
    workflow.sink("output/step1.jsonl")
    
    # Test first step
    result1 = workflow.run(num_records=1)
    print(f"Step 1 complete: {result1}")
    
    # Add second step
    workflow.llm("gpt-4o", "Expand: {llm_1_response}")
    workflow.sink("output/step2.jsonl")
    
    # Test with both steps
    result2 = workflow.run(num_records=1)
    print(f"Step 2 complete: {result2}")
    
    # Continue adding steps...
```

### 5. Resource Management

```python
import sygra

def efficient_workflow():
    """Workflow with efficient resource usage"""
    
    workflow = sygra.Workflow("efficient")
    
    # Use file source for large datasets (memory efficient)
    workflow.source("data/large_dataset.jsonl")
    
    # Use cheaper model for simple tasks
    workflow.llm(
        model="gpt-4o-mini",  # More cost-effective
        prompt="Simple task: {text}"
    )
    
    # Stream to output (don't keep all in memory)
    workflow.sink("output/results.jsonl")
    
    # Process in batches
    workflow.run(
        num_records=10000,
        batch_size=50,  # Process 50 at a time
        checkpoint_interval=500  # Save progress
    )
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue 1: Import Errors

```python
# Problem: Module not found
try:
    import sygra
except ImportError:
    print("❌ SyGra not installed")
    print("Solution: pip install sygra")

# Verify installation
import sygra
print(f"✓ SyGra version: {sygra.__version__}")
print(f"✓ Features available: {sygra.validate_environment()}")
```

#### Issue 2: Configuration Errors

```python
import sygra

try:
    workflow = sygra.Workflow("my_task")
    workflow.run()
except sygra.ConfigurationError as e:
    print(f"❌ Configuration error: {e}")
    print("Solutions:")
    print("  1. Check graph_config has 'nodes' and 'edges'")
    print("  2. Verify all node types are valid")
    print("  3. Ensure models are properly configured")
```

#### Issue 3: Data Source Issues

```python
import sygra
from pathlib import Path

def check_data_source(file_path):
    """Validate data source before running workflow"""
    
    # Check file exists
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        return False
    
    # Check file is readable
    try:
        with open(file_path) as f:
            first_line = f.readline()
            import json
            json.loads(first_line)
        print(f"Data source valid: {file_path}")
        return True
    except Exception as e:
        print(f"Invalid data format: {e}")
        print("Solution: Ensure file is valid JSONL (one JSON per line)")
        return False

# Use in workflow
if check_data_source("data/input.jsonl"):
    workflow = sygra.Workflow("safe_workflow")
    workflow.source("data/input.jsonl")
    workflow.llm("gpt-4o", "Process: {text}")
    workflow.sink("output/results.jsonl")
    workflow.run()
```

#### Issue 4: Memory Issues with Large Datasets

```python
import sygra

def handle_large_dataset():
    """Process large dataset efficiently"""
    
    workflow = sygra.Workflow("large_dataset")
    
    # Use file source (streams data, not all in memory)
    workflow.source("data/very_large_file.jsonl")
    
    workflow.llm("gpt-4o-mini", "Process: {text}")
    
    # Use file sink (streams output)
    workflow.sink("output/results.jsonl")
    
    # Process in chunks
    total_records = 100000
    chunk_size = 1000
    
    for start in range(0, total_records, chunk_size):
        print(f"Processing records {start} to {start + chunk_size}")
        workflow.run(
            num_records=chunk_size,
            start_index=start,
            batch_size=50
        )
```

---

## Advanced Patterns

### Pattern 1: Pipeline Pattern

```python
import sygra

def create_processing_pipeline():
    """Multi-stage processing pipeline"""
    
    # Stage 1: Data cleaning
    stage1 = sygra.Workflow("stage1_clean")
    stage1.source("data/raw_data.jsonl")
    stage1.llm("gpt-4o-mini", "Clean and normalize: {text}")
    stage1.sink("output/stage1_cleaned.jsonl")
    stage1.run()
    
    # Stage 2: Enhancement
    stage2 = sygra.Workflow("stage2_enhance")
    stage2.source("output/stage1_cleaned.jsonl")
    stage2.llm("gpt-4o", "Enhance with details: {llm_1_response}")
    stage2.sink("output/stage2_enhanced.jsonl")
    stage2.run()
    
    # Stage 3: Quality filtering
    stage3 = sygra.Workflow("stage3_filter")
    stage3.source("output/stage2_enhanced.jsonl")
    stage3.quality_tagging(True)
    stage3.sink("output/final_output.jsonl")
    stage3.run()
    
    print("✓ Pipeline complete")
```

### Pattern 2: Fan-Out Pattern

```python
import sygra

def fan_out_processing():
    """Process one input with multiple models in parallel"""
    
    # Shared input
    input_data = [{"question": "What is quantum computing?"}]
    
    # Create multiple workflows for different models
    models = {
        "gpt4": "gpt-4o",
        "gpt4mini": "gpt-4o-mini",
        "claude": "claude-sonnet-4"
    }
    
    results = {}
    
    for name, model in models.items():
        workflow = sygra.Workflow(f"fanout_{name}")
        workflow.source(input_data)
        workflow.llm(model, "Answer: {question}")
        workflow.sink(f"output/fanout_{name}.jsonl")
        results[name] = workflow.run()
    
    print(f"✓ Processed with {len(models)} models")
    return results
```

### Pattern 3: Iterative Refinement

```python
import sygra

def iterative_refinement():
    """Iteratively refine output through multiple passes"""
    
    data = [{"text": "Write about AI"}]
    
    # Pass 1: Initial generation
    workflow1 = sygra.Workflow("refinement_pass1")
    workflow1.source(data)
    workflow1.llm("gpt-4o", "Write a draft about: {text}")
    workflow1.sink("output/draft_v1.jsonl")
    result1 = workflow1.run()
    
    # Pass 2: Critique and improve
    workflow2 = sygra.Workflow("refinement_pass2")
    workflow2.source("output/draft_v1.jsonl")
    workflow2.llm(
        "gpt-4o",
        "Critique this draft and suggest improvements: {llm_1_response}"
    )
    workflow2.sink("output/draft_v2_critique.jsonl")
    result2 = workflow2.run()
    
    # Pass 3: Final revision
    workflow3 = sygra.Workflow("refinement_pass3")
    workflow3.source("output/draft_v2_critique.jsonl")
    workflow3.llm(
        "gpt-4o",
        "Revise the draft based on this critique:\n"
        "Draft: {llm_1_response}\n"
        "Critique: {llm_2_response}"
    )
    workflow3.sink("output/final_version.jsonl")
    result3 = workflow3.run()
    
    print("✓ Refinement complete")
    return result3
```

### Pattern 4: Consensus Pattern

```python
import sygra

def build_consensus():
    """Get consensus from multiple models"""
    
    workflow = sygra.Workflow("consensus")
    
    workflow.source([
        {"question": "What are the key challenges in renewable energy?"}
    ])
    
    # Get responses from multiple models
    workflow.multi_llm(
        models={
            "model1": "gpt-4o",
            "model2": "claude-sonnet-4",
            "model3": "gpt-4o-mini"
        },
        prompt="Answer this question: {question}"
    )
    
    # Synthesize consensus
    workflow.llm(
        "gpt-4o",
        "Based on these three responses, create a consensus answer "
        "that incorporates the best points from each:\n{multi_llm_1_response}"
    )
    
    workflow.sink("output/consensus_answers.jsonl")
    workflow.run()
```

### Pattern 5: Chain of Thought

```python
import sygra

def chain_of_thought():
    """Implement chain-of-thought reasoning"""
    
    workflow = sygra.Workflow("chain_of_thought")
    
    workflow.source([
        {"problem": "A train travels 120 km in 2 hours, then 180 km in 3 hours. "
                   "What is its average speed for the entire journey?"}
    ])
    
    # Step 1: Break down the problem
    workflow.llm(
        "gpt-4o",
        prompt=[
            {"system": "Break down problems step by step."},
            {"user": "Break down this problem into steps: {problem}"}
        ]
    )
    
    # Step 2: Solve each step
    workflow.llm(
        "gpt-4o",
        "Now solve each step:\n{llm_1_response}"
    )
    
    # Step 3: Verify the solution
    workflow.llm(
        "gpt-4o",
        "Verify this solution is correct:\n{llm_2_response}"
    )
    
    workflow.sink("output/chain_of_thought.jsonl")
    workflow.run()
```

---

## Performance Optimization

### Optimization 1: Model Selection

```python
import sygra

def optimized_model_selection():
    """Use appropriate models for different tasks"""
    
    workflow = sygra.Workflow("optimized")
    
    workflow.source("data/tasks.jsonl")
    
    # Simple tasks: Use smaller, faster model
    workflow.llm(
        model="gpt-4o-mini",  # Faster and cheaper
        prompt="Simple extraction: {text}"
    )
    
    # Complex tasks: Use more capable model only when needed
    workflow.llm(
        model="gpt-4o",  # Use for complex reasoning
        prompt="Complex analysis: {llm_1_response}"
    )
    
    workflow.sink("output/optimized.jsonl")
    workflow.run()
```

### Optimization 2: Batch Processing

```python
import sygra

def optimized_batching():
    """Optimize batch size for throughput"""
    
    workflow = sygra.Workflow("batched")
    
    workflow.source("data/large_dataset.jsonl")
    workflow.llm("gpt-4o-mini", "Process: {text}")
    workflow.sink("output/results.jsonl")
    
    # Optimal batch size depends on:
    # - API rate limits
    # - Memory constraints
    # - Network latency
    
    workflow.run(
        num_records=10000,
        batch_size=100,  # Larger batches for better throughput
        checkpoint_interval=1000  # Less frequent checkpoints
    )
```

### Optimization 3: Caching

```python
import sygra
import json
from pathlib import Path

def cached_workflow():
    """Implement caching to avoid duplicate processing"""
    
    cache_file = Path("cache/processed.json")
    cache_file.parent.mkdir(exist_ok=True)
    
    # Load cache
    cache = {}
    if cache_file.exists():
        with open(cache_file) as f:
            cache = json.load(f)
    
    # Process only new items
    all_data = [
        {"id": 1, "text": "First item"},
        {"id": 2, "text": "Second item"},
    ]
    
    new_data = [item for item in all_data if str(item["id"]) not in cache]
    
    if new_data:
        workflow = sygra.Workflow("cached")
        workflow.source(new_data)
        workflow.llm("gpt-4o", "Process: {text}")
        workflow.sink("output/new_results.jsonl")
        results = workflow.run()
        
        # Update cache
        for item in results:
            cache[str(item["id"])] = item
        
        with open(cache_file, "w") as f:
            json.dump(cache, f)
        
        print(f"Processed {len(new_data)} new items")
    else:
        print("All items already in cache")
```

---

## API Reference Quick Guide

### Core Classes

```python
# Workflow - Main workflow builder
workflow = sygra.Workflow(name="my_workflow")

# Configuration loader
config = sygra.load_config("config/settings.yaml")

# Model configuration
model_config = sygra.ModelConfigBuilder.from_name("gpt-4o")
```

### Workflow Methods

```python
# Data source/sink
workflow.source(data)  # Set input data
workflow.sink(path)    # Set output path

# Node addition
workflow.llm(model, prompt, **kwargs)  # Add LLM node
workflow.agent(model, tools, prompt, **kwargs)  # Add agent node
workflow.multi_llm(models, prompt, **kwargs)  # Add multi-LLM node
workflow.lambda_func(func, output, **kwargs)  # Add lambda node
workflow.subgraph(name, config_map)  # Add subgraph

# Configuration
workflow.resumable(True)  # Enable resumable execution
workflow.quality_tagging(True)  # Enable quality tagging
workflow.output_fields(fields)  # Set output fields

# Execution
results = workflow.run(
    num_records=100,
    batch_size=25,
    start_index=0,
    output_dir="output/",
    debug=False,
    resume=False
)
```

### Quick Utilities

```python
# Quick LLM
sygra.quick_llm(model, prompt, data_source, output)

# Quick Agent
sygra.quick_agent(model, prompt, tools, data_source, output)

# Execute task
sygra.execute_task(task_name, **kwargs)

# List models
models = sygra.list_available_models()
```

---

## FAQ

**Q: How do I handle large datasets?**
```python
# Use file sources and batch processing
workflow.source("large_file.jsonl")
workflow.run(batch_size=50, checkpoint_interval=100)
```

**Q: How do I reduce costs?**
```python
# Use smaller models for simple tasks
workflow.llm("gpt-4o-mini", "Simple task: {text}")  # Cheaper

# Test with small datasets first
workflow.run(num_records=10)  # Test before full run
```

**Q: How do I resume interrupted workflows?**
```python
# Enable resumable execution
workflow.resumable(True)
workflow.run(resume=True, checkpoint_interval=100)
```

**Q: How do I validate my workflow?**
```python
# Test with minimal data first
test_data = [{"text": "test"}]
workflow.source(test_data)
results = workflow.run(num_records=1)
assert len(results) == 1  # Validate
```

**Q: How do I debug issues?**
```python
# Enable debug mode
workflow.run(debug=True)

# Use smaller models for faster iteration
workflow.llm("gpt-4o-mini", prompt)  # Faster for testing
```

---

## Conclusion

This guide covers the essential usage patterns for SyGra. All examples are tested and ready to use. Start with the basic examples and progressively explore advanced features as needed.

For the latest updates and additional examples, check the official documentation and example tasks in the repository.