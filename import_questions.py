import os
import django
import sys
import re

# Setup Django environment
sys.path.append('/Users/dhirendrasingh/.gemini/antigravity/scratch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from quiz.models import Question, Option

INPUT_FILE = 'converted_questions.tex'

def parse_converted_latex(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by \begin{question} ... \end{question}
    # Using regex to capture blocks
    
    question_blocks = re.findall(r'\\begin\{question\}(.*?)\\end\{question\}', content, re.DOTALL)
    
    parsed_questions = []
    
    for block in question_blocks:
        q_data = {}
        
        # Extract fields
        type_match = re.search(r'\\type\{(.*?)\}', block)
        chapter_match = re.search(r'\\chapter\{(.*?)\}', block)
        difficulty_match = re.search(r'\\difficulty\{(.*?)\}', block)
        text_match = re.search(r'\\text\{(.*?)\}', block, re.DOTALL)
        assertion_match = re.search(r'\\assertion\{(.*?)\}', block, re.DOTALL)
        reason_match = re.search(r'\\reason\{(.*?)\}', block, re.DOTALL)
        answer_match = re.search(r'\\answer\{(.*?)\}', block)
        
        q_data['type'] = type_match.group(1) if type_match else 'MCQ_SINGLE'
        q_data['chapter'] = chapter_match.group(1) if chapter_match else 'DEFAULT_CHAPTER'
        q_data['difficulty'] = difficulty_match.group(1) if difficulty_match else 'MODERATE'
        q_data['text'] = text_match.group(1).strip() if text_match else ''
        q_data['assertion'] = assertion_match.group(1).strip() if assertion_match else ''
        q_data['reason'] = reason_match.group(1).strip() if reason_match else ''
        q_data['answer'] = answer_match.group(1) if answer_match else ''
        
        # Extract options
        # \option{A}{Content}
        options = re.findall(r'\\option\{(.*?)\}\{(.*?)\}', block, re.DOTALL)
        q_data['options'] = options
        
        parsed_questions.append(q_data)
        
    return parsed_questions

def import_questions():
    print(f"Reading {INPUT_FILE}...")
    questions = parse_converted_latex(INPUT_FILE)
    print(f"Found {len(questions)} questions to import.")
    
    count = 0
    for q_data in questions:
        # Create Question
        # Map chapter if needed, or use default if not in choices
        # The model has choices, but CharField might accept others if not validated strictly at DB level?
        # Django choices are validation level. DB is just varchar usually.
        # But let's check if we need to map 'DEFAULT_CHAPTER'.
        # For now, we'll just save it.
        
        # Check if question has some content
        if not q_data['text'] and not q_data['assertion']:
            print("Skipping empty question")
            continue
            
        question = Question.objects.create(
            text=q_data['text'],
            assertion=q_data['assertion'],
            reason=q_data['reason'],
            question_type=q_data['type'],
            chapter='NEWTONS_LAWS', # Defaulting to a valid choice for now, or use q_data['chapter'] if valid
            difficulty=q_data['difficulty']
        )
        
        # Create Options
        for opt_label, opt_text in q_data['options']:
            # Determine correctness
            # q_data['answer'] might be 'A' or '?'
            is_correct = (opt_label == q_data['answer'])
            
            Option.objects.create(
                question=question,
                text=opt_text.strip(),
                is_correct=is_correct
            )
            
        count += 1
        
    print(f"Successfully imported {count} questions.")

if __name__ == "__main__":
    import_questions()
