import os
import re
import glob

def linearize_tables(text):
    """
    Finds markdown tables in text and converts them into linear bullet points.
    """
    lines = text.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if current line might be a header and next line is a separator
        is_table = False
        if '|' in line and i + 1 < len(lines):
            next_line = lines[i+1]
            # Simple regex for markdown table separator: contains only |, -, :, space
            if re.match(r'^\s*\|?[\s\-\:]+\|[\s\-\:\|]*$', next_line) and '-' in next_line:
                is_table = True
                
        if is_table:
            # 1. Parse headers
            raw_headers = line.strip().strip('|').split('|')
            headers = [h.strip() for h in raw_headers]
            
            # If previous line wasn't blank, add one for spacing
            if len(new_lines) > 0 and new_lines[-1].strip() != "":
                new_lines.append("")
            
            # Skip header and separator line
            i += 2
            
            # 2. Parse data rows
            while i < len(lines):
                data_line = lines[i].strip()
                # A row must have '|' to be part of the table
                if not data_line or '|' not in data_line:
                    break
                
                raw_data = data_line.strip('|').split('|')
                data = [d.strip() for d in raw_data]
                
                # Zip headers and data together
                row_str_parts = []
                for j in range(min(len(headers), len(data))):
                    h = headers[j]
                    d = data[j]
                    # Only append if cell is not empty
                    if d: 
                        if h:
                            row_str_parts.append(f"{h}: {d}")
                        else:
                            row_str_parts.append(f"{d}")
                
                if row_str_parts:
                    new_lines.append("- " + ". ".join(row_str_parts) + ".")
                
                i += 1
                
            new_lines.append("") # Blank line after the linearized table
            continue
        else:
            new_lines.append(line)
            i += 1
            
    return '\n'.join(new_lines)

def clean_markdown_text(text):
    # 1. Linearize tables first so they don't get broken by other steps
    text = linearize_tables(text)

    # 2. Remove image tags: ![alt](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    
    # 3. Extract text from links: [text](url) -> text (run multiple times for nested)
    for _ in range(3):
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
    # 4. Clean up completely empty links like []() or [](url) left by image removal
    text = re.sub(r'\[\]\([^\)]*\)', '', text)
    
    # Split into lines for line-by-line cleaning
    lines = text.split('\n')
    cleaned_lines = []
    
    # Noise words to drop
    noise_exact_matches = {'previous', 'next', 'see more', 'breaking news', 'general news'}
    
    for line in lines:
        original_line = line
        line = line.strip()
        line_lower = line.lower()
        
        # Skip pagination like "* 1", "* 2"
        if re.match(r'^\*\s+\d+$', line):
            continue
            
        # Skip exact noise matches (ignoring leading #)
        clean_line_lower = re.sub(r'^#+\s*', '', line_lower).strip()
        if clean_line_lower in noise_exact_matches:
            continue
            
        # Skip single uppercase characters standing alone (like E, C, L, X)
        if len(line) == 1 and line.isalpha() and line.isupper():
            continue
            
        cleaned_lines.append(original_line)
        
    text = '\n'.join(cleaned_lines)
    
    # 5. Deduplicate paragraphs (blocks separated by empty lines)
    paragraphs = re.split(r'\n\s*\n', text)
    seen_paragraphs = set()
    deduped_paragraphs = []
    
    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        if p_clean not in seen_paragraphs:
            seen_paragraphs.add(p_clean)
            deduped_paragraphs.append(p_clean)
            
    final_text = '\n\n'.join(deduped_paragraphs)
    
    return final_text

def main():
    # Setup robust paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    base_dir = os.path.join(project_root, "data", "standardized")
    output_dir = os.path.join(project_root, "data", "cleaned_rag")
    
    md_files = glob.glob(f"{base_dir}/**/*.md", recursive=True)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Found {len(md_files)} markdown files.")
    print("Starting cleaning and Table Linearization...")
    
    for file_path in md_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        cleaned_content = clean_markdown_text(content)
        
        # Preserve directory structure
        rel_path = os.path.relpath(file_path, base_dir)
        out_path = os.path.join(output_dir, rel_path)
        
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
            
        print(f"Processed: {rel_path}")
        
    print(f"\nAll done! Perfect RAG data saved to: {output_dir}")

if __name__ == "__main__":
    main()
