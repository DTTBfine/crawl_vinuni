import os
import re
import glob

def clean_markdown_text(text):
    # 1. Remove image tags: ![alt](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    
    # 2. Extract text from links: [text](url) -> text
    # Run a few times in case of nested links, though rare
    for _ in range(3):
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Split into lines for line-by-line cleaning
    lines = text.split('\n')
    cleaned_lines = []
    
    # Noise patterns to drop completely
    noise_exact_matches = {'previous', 'next', 'see more', 'breaking news', 'general news'}
    
    for line in lines:
        original_line = line
        line = line.strip()
        line_lower = line.lower()
        
        # Skip pagination like "* 1", "* 2"
        if re.match(r'^\*\s+\d+$', line):
            continue
            
        # Skip exact noise matches (ignoring case and surrounding spaces/hashes)
        clean_line_lower = re.sub(r'^#+\s*', '', line_lower).strip()
        if clean_line_lower in noise_exact_matches:
            continue
            
        # Skip single characters that are uppercase letters (like E, C, L, X alone on a line)
        if len(line) == 1 and line.isalpha() and line.isupper():
            continue
            
        cleaned_lines.append(original_line)
        
    # Rejoin lines
    text = '\n'.join(cleaned_lines)
    
    # 3. Deduplicate paragraphs (blocks separated by empty lines)
    # This helps remove repeated sections like the "2025" events duplicated at the bottom
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
            
    # Join with double newlines
    final_text = '\n\n'.join(deduped_paragraphs)
    
    return final_text

def main():
    base_dir = "data/standardized"
    md_files = glob.glob(f"{base_dir}/**/*.md", recursive=True)
    
    output_dir = "data/cleaned"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Found {len(md_files)} markdown files. Starting cleaning...")
    
    for file_path in md_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        cleaned_content = clean_markdown_text(content)
        
        # Create output path preserving the directory structure
        rel_path = os.path.relpath(file_path, base_dir)
        out_path = os.path.join(output_dir, rel_path)
        
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
            
        print(f"Cleaned: {rel_path}")
        
    print(f"\nAll files have been cleaned and saved to '{output_dir}'.")

if __name__ == "__main__":
    main()
