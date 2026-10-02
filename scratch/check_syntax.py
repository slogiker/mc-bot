def check_quotes(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    in_double_quote = False
    escape = False
    i = 0
    n = len(content)
    line = 1
    
    while i < n:
        char = content[i]
        if char == '\n':
            line += 1
            
        if escape:
            escape = False
            i += 1
            continue
            
        if char == '\\':
            escape = True
            i += 1
            continue
            
        if char == '"':
            in_double_quote = not in_double_quote
            print(f"Double quote {'OPENED' if in_double_quote else 'CLOSED'} on line {line}")
            
        i += 1

if __name__ == '__main__':
    check_quotes('install/install.sh')
