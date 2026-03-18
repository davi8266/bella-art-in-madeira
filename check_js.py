
def check_balance(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    stack = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        for j, char in enumerate(line):
            if char in '{[(':
                stack.append((char, i+1, j+1))
            elif char in '}])':
                if not stack:
                    print(f"Unmatched {char} at line {i+1} col {j+1}")
                    return False
                last, li, lj = stack.pop()
                if (last == '{' and char != '}') or \
                   (last == '[' and char != ']') or \
                   (last == '(' and char != ')'):
                    print(f"Mismatched {last} (from {li}:{lj}) with {char} at line {i+1} col {j+1}")
                    return False
    
    if stack:
        last, li, lj = stack[0]
        print(f"Unclosed {last} at line {li} col {lj}")
        return False
        
    print("Balance check passed")
    return True

check_balance('web/app.js')
