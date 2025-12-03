import re
import os
from django.core.management.base import BaseCommand, CommandError
from quiz.models import Question, Option

class Command(BaseCommand):
    help = 'Import questions from a LaTeX file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the LaTeX file')

    def handle(self, *args, **options):
        file_path = options['file_path']

        if not os.path.exists(file_path):
            raise CommandError(f'File "{file_path}" does not exist')
            
        base_dir = os.path.dirname(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split content into question blocks
        question_blocks = re.findall(r'\\begin\{question\}(.*?)\\end\{question\}', content, re.DOTALL)

        self.stdout.write(f'Found {len(question_blocks)} questions. Processing...')

        count = 0
        for block in question_blocks:
            try:
                self.process_question(block, base_dir)
                count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error processing question: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} questions'))

    def parse_braced_content(self, text, start_index):
        """
        Parses content enclosed in braces {}, handling nesting.
        Returns (content, end_index)
        """
        if start_index >= len(text) or text[start_index] != '{':
            return None, start_index

        balance = 1
        i = start_index + 1
        content_start = i
        
        while i < len(text) and balance > 0:
            if text[i] == '{':
                balance += 1
            elif text[i] == '}':
                balance -= 1
            i += 1
            
        if balance == 0:
            return text[content_start:i-1], i
        return None, i

    def extract_command_value(self, text, command):
        """
        Extracts the value of a command like \command{value}.
        """
        pattern = r'\\' + command
        match = re.search(pattern, text)
        if match:
            content, _ = self.parse_braced_content(text, match.end())
            return content.strip() if content else None
        return None

    def process_question(self, block, base_dir):
        # Type
        q_type = self.extract_command_value(block, 'type') or 'MCQ_SINGLE'
        
        # Chapter
        chapter = self.extract_command_value(block, 'chapter')
        
        # Difficulty
        difficulty = self.extract_command_value(block, 'difficulty') or 'MODERATE'
        
        # Text
        text = self.extract_command_value(block, 'text')
        if not text:
            raise ValueError("Question text is missing")
            
        # Check for image in text
        image_path = None
        img_match = re.search(r'\\includegraphics\{(.*?)\}', text)
        if img_match:
            img_rel_path = img_match.group(1)
            # Remove the image command from text
            text = text.replace(img_match.group(0), '').strip()
            
            full_img_path = os.path.join(base_dir, img_rel_path)
            if os.path.exists(full_img_path):
                image_path = full_img_path
            else:
                self.stderr.write(self.style.WARNING(f'Image not found: {full_img_path}'))

        # Create Question
        question = Question.objects.create(
            text=text,
            question_type=q_type,
            chapter=chapter,
            difficulty=difficulty
        )
        
        if image_path:
            from django.core.files import File
            with open(image_path, 'rb') as img_f:
                question.image.save(os.path.basename(image_path), File(img_f))
        
        if q_type == 'MATRIX':
            # Parse Rows
            rows = []
            # Find all occurrences of \row
            # We use a lookahead or just iterate and skip if we've processed it?
            # Better: finditer returns matches in order.
            # But if we use r'\\row', we might match \row in text? Unlikely if we assume valid LaTeX structure.
            # Let's use r'\\row\s*\{' to be safer, but parse_braced_content expects '{' at start.
            # Actually, parse_braced_content checks text[start_index] == '{'.
            # So if we match r'\\row', match.end() is before '{'.
            # We need to handle potential whitespace? LaTeX allows `\row {A}`.
            # Let's assume standard format `\row{` for now or handle whitespace.
            
            row_pattern = r'\\row'
            for match in re.finditer(row_pattern, block):
                # We need to ensure this is actually a command, not part of a word like \rowboat (unlikely but possible)
                # And check if it's followed by {
                
                # Simple check: look ahead for {
                start = match.end()
                # Skip whitespace
                while start < len(block) and block[start].isspace():
                    start += 1
                
                if start < len(block) and block[start] == '{':
                    r_id, end1 = self.parse_braced_content(block, start)
                    
                    # Skip whitespace again
                    while end1 < len(block) and block[end1].isspace():
                        end1 += 1
                        
                    r_text, end2 = self.parse_braced_content(block, end1)
                    
                    if r_id and r_text:
                        r_image_path = None
                        r_img_match = re.search(r'\\includegraphics\{(.*?)\}', r_text)
                        if r_img_match:
                            r_img_rel_path = r_img_match.group(1)
                            r_text = r_text.replace(r_img_match.group(0), '').strip()
                            full_r_img_path = os.path.join(base_dir, r_img_rel_path)
                            if os.path.exists(full_r_img_path):
                                from django.core.files.storage import default_storage
                                from django.core.files.base import ContentFile
                                
                                with open(full_r_img_path, 'rb') as f:
                                    saved_path = default_storage.save(f'matrix_images/{os.path.basename(full_r_img_path)}', ContentFile(f.read()))
                                    r_image_path = default_storage.url(saved_path)

                        rows.append({
                            "id": r_id,
                            "text": r_text.strip(),
                            "image": r_image_path
                        })

            # Parse Cols
            cols = []
            col_pattern = r'\\col'
            for match in re.finditer(col_pattern, block):
                start = match.end()
                while start < len(block) and block[start].isspace():
                    start += 1
                    
                if start < len(block) and block[start] == '{':
                    c_id, end1 = self.parse_braced_content(block, start)
                    while end1 < len(block) and block[end1].isspace():
                        end1 += 1
                    c_text, end2 = self.parse_braced_content(block, end1)
                    
                    if c_id and c_text:
                        c_image_path = None
                        c_img_match = re.search(r'\\includegraphics\{(.*?)\}', c_text)
                        if c_img_match:
                            c_img_rel_path = c_img_match.group(1)
                            c_text = c_text.replace(c_img_match.group(0), '').strip()
                            full_c_img_path = os.path.join(base_dir, c_img_rel_path)
                            if os.path.exists(full_c_img_path):
                                from django.core.files.storage import default_storage
                                from django.core.files.base import ContentFile
                                with open(full_c_img_path, 'rb') as f:
                                    saved_path = default_storage.save(f'matrix_images/{os.path.basename(full_c_img_path)}', ContentFile(f.read()))
                                    c_image_path = default_storage.url(saved_path)

                        cols.append({
                            "id": c_id,
                            "text": c_text.strip(),
                            "image": c_image_path
                        })

            # Parse Answers
            correct = {}
            ans_pattern = r'\\matrix_answer'
            for match in re.finditer(ans_pattern, block):
                start = match.end()
                while start < len(block) and block[start].isspace():
                    start += 1
                    
                if start < len(block) and block[start] == '{':
                    row_id, end1 = self.parse_braced_content(block, start)
                    while end1 < len(block) and block[end1].isspace():
                        end1 += 1
                    col_ids_str, end2 = self.parse_braced_content(block, end1)
                    
                    if row_id and col_ids_str:
                        col_ids = [c.strip() for c in col_ids_str.split(',')]
                        correct[row_id] = col_ids
            
            question.matrix_config = {
                "rows": rows,
                "cols": cols,
                "correct": correct
            }
            question.save()

        else:
            # Options for MCQ/Numerical
            # We need to iterate through the block to find all \option commands
            # Since regex is tricky with nested braces, we'll search iteratively
            
            option_pattern = r'\\option'
            for match in re.finditer(option_pattern, block):
                start = match.end()
                # First brace: Label
                label, end1 = self.parse_braced_content(block, start)
                # Second brace: Text
                opt_text, end2 = self.parse_braced_content(block, end1)
                
                if label and opt_text is not None:
                    # Check for image in option text
                    opt_image_path = None
                    opt_img_match = re.search(r'\\includegraphics\{(.*?)\}', opt_text)
                    if opt_img_match:
                        opt_img_rel_path = opt_img_match.group(1)
                        opt_text = opt_text.replace(opt_img_match.group(0), '').strip()
                        
                        full_opt_img_path = os.path.join(base_dir, opt_img_rel_path)
                        if os.path.exists(full_opt_img_path):
                            opt_image_path = full_opt_img_path
                        else:
                            self.stderr.write(self.style.WARNING(f'Option image not found: {full_opt_img_path}'))

                    # Determine correctness
                    # We need to find the answer first or check it later. 
                    # Let's extract answer at the top level or just check here if we have it.
                    # Actually, let's just create the option and set is_correct later.
                    
                    option = Option.objects.create(
                        question=question,
                        text=opt_text.strip()
                    )
                    
                    if opt_image_path:
                        from django.core.files import File
                        with open(opt_image_path, 'rb') as opt_img_f:
                            option.image.save(os.path.basename(opt_image_path), File(opt_img_f))
                            
                    # Store label temporarily if needed, but we need to match with answer
                    # Let's assume the answer command uses the same label
                    
            # Answer
            answer_label = self.extract_command_value(block, 'answer')
            if answer_label:
                # We need to map labels to options. 
                # Since we didn't store labels in the DB, we have to rely on the order or re-parse.
                # A better approach: Store options in a list first.
                pass
                
            # Re-doing options logic to handle correctness
            question.options.all().delete() # Clear partial options
            
            options_data = []
            for match in re.finditer(option_pattern, block):
                start = match.end()
                label, end1 = self.parse_braced_content(block, start)
                opt_text, end2 = self.parse_braced_content(block, end1)
                
                if label and opt_text is not None:
                    options_data.append({
                        'label': label,
                        'text': opt_text,
                        'is_correct': (label == answer_label)
                    })

            for opt_data in options_data:
                opt_text = opt_data['text']
                opt_image_path = None
                
                opt_img_match = re.search(r'\\includegraphics\{(.*?)\}', opt_text)
                if opt_img_match:
                    opt_img_rel_path = opt_img_match.group(1)
                    opt_text = opt_text.replace(opt_img_match.group(0), '').strip()
                    full_opt_img_path = os.path.join(base_dir, opt_img_rel_path)
                    if os.path.exists(full_opt_img_path):
                        opt_image_path = full_opt_img_path

                option = Option.objects.create(
                    question=question,
                    text=opt_text.strip(),
                    is_correct=opt_data['is_correct']
                )
                
                if opt_image_path:
                    from django.core.files import File
                    with open(opt_image_path, 'rb') as opt_img_f:
                        option.image.save(os.path.basename(opt_image_path), File(opt_img_f))

        self.stdout.write(f'Imported question: {text[:30]}...')
