import bibtexparser

def format_authors(author_string):
    if not author_string:
        return ""
    
    authors = author_string.split(' and ')
    formatted_authors = []
    
    for author in authors:
        author = author.strip()
        if ',' in author:
            parts = author.split(',', 1)
            name = f"{parts[1].strip()} {parts[0].strip()}"
            formatted_authors.append(name)
        else:
            formatted_authors.append(author)
            
    if len(formatted_authors) == 1:
        return formatted_authors[0]
    elif len(formatted_authors) == 2:
        return f"{formatted_authors[0]} and {formatted_authors[1]}"
    else:
        return ", ".join(formatted_authors[:-1]) + f", and {formatted_authors[-1]}"

# 读取 bib 文件
with open('docs/publications.bib', 'r', encoding='utf-8') as bibtex_file:
    bib_database = bibtexparser.load(bibtex_file)

# 只提取 @article
articles = [
    entry for entry in bib_database.entries 
    if entry.get('ENTRYTYPE', '').lower() == 'article'
]

# 按年份降序
sorted_articles = sorted(articles, key=lambda x: x.get('year', '0'), reverse=True)

markdown_content = "# Publications\n\n"
current_year = ""

for entry in sorted_articles:
    year = entry.get('year', 'Unknown')
    if year != current_year:
        markdown_content += f"## {year}\n\n"
        current_year = year
        
    title = entry.get('title', '').replace('{', '').replace('}', '')
    journal = entry.get('journal', entry.get('booktitle', ''))
    
    # 作者处理与下划线逻辑
    raw_author = entry.get('author', '')
    author_str = format_authors(raw_author)
    author_str = author_str.replace('Hao Ou', '<u>Hao Ou</u>')
    
    # --- 新增：提取卷号和页码 ---
    volume = entry.get('volume', '')
    pages = entry.get('pages', '').replace('--', '-') # 将双破折号替换为更美观的单破折号
    
    # 组装正规的出版信息格式：*Journal*, **Volume**, Pages (Year)
    pub_info = f"*{journal}*"
    if volume:
        pub_info += f", **{volume}**"
    if pages:
        pub_info += f", {pages}"
    if year and year != 'Unknown':
        pub_info += f" ({year})"
    # ----------------------------
    
    # 超链接逻辑
    url = entry.get('url', '').strip()
    doi = entry.get('doi', '').strip()
    target_link = url if url else (f"https://doi.org/{doi}" if doi else "")
    formatted_title = f"[{title}]({target_link})" if target_link else title

    # 拼接单条记录 (尾部使用拼装好的 pub_info)
    markdown_content += f"- {author_str}. **\"{formatted_title}\"**. {pub_info}.\n"

# 写入文件
with open('docs/publications.md', 'w', encoding='utf-8') as md_file:
    md_file.write(markdown_content)

print("Publications generated with volume, pages, and formal formatting!")