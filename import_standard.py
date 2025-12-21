import os
import django
import sys
import re
from django.core.files import File

# Setup Django environment
sys.path.append('/Users/dhirendrasingh/.gemini/antigravity/scratch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from quiz.models import Question, Option, MatrixRow, MatrixCol, SolutionBlock

def parse_and_import(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all question blocks
    blocks = re.findall(r'\\begin\{question\}(.*?)\\end\{question\}', content, re.DOTALL)
    print(f"Found {len(blocks)} questions in {file_path}")

    for block in blocks:
        try:
            # Extract basic fields
            q_type = (re.search(r'\\type\{(.*?)\}', block) or re.search(r'\\type\s+(.*)', block)).group(1).strip()
            chapter = (re.search(r'\\chapter\{(.*?)\}', block) or re.search(r'\\chapter\s+(.*)', block)).group(1).strip()
            difficulty = (re.search(r'\\difficulty\{(.*?)\}', block) or re.search(r'\\difficulty\s+(.*)', block)).group(1).strip()
            
            # Partial Marking (Optional)
            partial_match = re.search(r'\\partial_marking\{(.*?)\}', block)
            allow_partial = True
            if partial_match:
                allow_partial = partial_match.group(1).strip().lower() == 'true'
            
            # Text, Assertion, Reason (Optional)
            text_match = re.search(r'\\text\{(.*?)\}', block, re.DOTALL)
            text = text_match.group(1).strip() if text_match else ""
            
            assertion_match = re.search(r'\\assertion\{(.*?)\}', block, re.DOTALL)
            assertion = assertion_match.group(1).strip() if assertion_match else ""
            
            reason_match = re.search(r'\\reason\{(.*?)\}', block, re.DOTALL)
            reason = reason_match.group(1).strip() if reason_match else ""
            
            answer = (re.search(r'\\answer\{(.*?)\}', block) or re.search(r'\\answer\s+(.*)', block)).group(1).strip()

            # Create Question object
            question = Question.objects.create(
                text=text,
                assertion=assertion,
                reason=reason,
                question_type=q_type,
                chapter=chapter,
                difficulty=difficulty,
                allow_partial_marking=allow_partial
            )

            # Handle Image if in \text using \includegraphics
            img_match = re.search(r'\\includegraphics.*?\{(.*?)\}', block)
            if img_match:
                img_path = img_match.group(1).strip()
                if os.path.exists(img_path):
                    with open(img_path, 'rb') as f_img:
                        question.image.save(os.path.basename(img_path), File(f_img), save=True)

            # Parse Options
            options = re.findall(r'\\option\{(.*?)\}\{(.*?)\}', block, re.DOTALL)
            for opt_label, opt_text in options:
                is_correct = (opt_label == answer)
                Option.objects.create(
                    question=question,
                    text=opt_text.strip(),
                    is_correct=is_correct
                )

            # Parse Matrix Rows & Cols
            rows = re.findall(r'\\row\{(.*?)\}\{(.*?)\}', block, re.DOTALL)
            for r_label, r_text in rows:
                # Answer might look like (A)-p, (B)-q
                # Extract matches for this row
                match_val = ""
                # Simple logic for (A)-p style
                if f"({r_label})-" in answer:
                    m = re.search(rf'\({r_label}\)-([\w,]+)', answer)
                    if m: match_val = m.group(1)
                
                MatrixRow.objects.create(question=question, label=r_label, text=r_text.strip(), matches=match_val)

            cols = re.findall(r'\\col\{(.*?)\}\{(.*?)\}', block, re.DOTALL)
            for c_label, c_text in cols:
                MatrixCol.objects.create(question=question, label=c_label, text=c_text.strip())

            # Parse Solution
            solution_match = re.search(r'\\solution\{(.*?)\}', block, re.DOTALL)
            if solution_match:
                sol_text = solution_match.group(1).strip()
                sb = SolutionBlock.objects.create(question=question, text=sol_text, order=1)
                
                # Check for solution image
                sol_img_match = re.search(r'\\sol_image\{(.*?)\}', block)
                if sol_img_match:
                    sol_img_path = sol_img_match.group(1).strip()
                    if os.path.exists(sol_img_path):
                        with open(sol_img_path, 'rb') as f_sol:
                            sb.image.save(os.path.basename(sol_img_path), File(f_sol), save=True)

            # Handle Numerical Answer
            if q_type == 'NUMERICAL':
                try:
                    question.numerical_answer = float(answer)
                    question.save()
                except ValueError:
                    pass

            print(f"Imported Q ID: {question.id} [{q_type}]")

        except Exception as e:
            print(f"Error importing question block: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parse_and_import(sys.argv[1])
    else:
        print("Usage: python import_standard.py path_to_latex_file.tex")
