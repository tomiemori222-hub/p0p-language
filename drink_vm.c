#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#endif

#define MAX_CMDS 5000
#define MAX_STACK 1000
#define MAX_VARS 100

// Структура для хранения значений (число или строка)
typedef struct {
    int is_string;
    int num;
    char str[256];
} Value;

Value stack[MAX_STACK];
int sp = 0; // Stack pointer

char var_names[MAX_VARS][50];
Value var_values[MAX_VARS];
int var_count = 0;

// Метки (Labels) для прыжков (jumps)
char label_names[100][50];
int label_indexes[100];
int label_count = 0;

// --- ФУНКЦИИ СТЕКА ---
void push_int(int n) {
    stack[sp].is_string = 0;
    stack[sp].num = n;
    sp++;
}

void push_str(const char* s) {
    stack[sp].is_string = 1;
    strncpy(stack[sp].str, s, 255);
    stack[sp].str[255] = '\0';
    sp++;
}

Value pop() {
    return stack[--sp];
}

// --- ФУНКЦИИ ПЕРЕМЕННЫХ ---
int find_var(const char* name) {
    for (int i = 0; i < var_count; i++) {
        if (strcmp(var_names[i], name) == 0) return i;
    }
    return -1;
}

void set_var(const char* name, Value val) {
    int idx = find_var(name);
    if (idx == -1) {
        strncpy(var_names[var_count], name, 49);
        var_values[var_count] = val;
        var_count++;
    } else {
        var_values[idx] = val;
    }
}

Value get_var(const char* name) {
    int idx = find_var(name);
    if (idx != -1) return var_values[idx];
    Value empty = {0, 0, ""};
    return empty;
}

// --- ПОИСК МЕТКИ ---
int get_label_index(const char* name) {
    for (int i = 0; i < label_count; i++) {
        if (strcmp(label_names[i], name) == 0) return label_indexes[i];
    }
    return -1;
}

int main(int argc, char* argv[]) {
    #ifdef _WIN32
    SetConsoleOutputCP(65001); // Включаем UTF-8 для корректного вывода
    #endif

    if (argc < 2) {
        printf("Usage: drink_vm <file.drink>\n");
        return 1;
    }

    FILE* file = fopen(argv[1], "r");
    if (!file) {
        printf("Error: Cannot open file %s\n", argv[1]);
        return 1;
    }

    // Читаем команды
    char* commands[MAX_CMDS];
    int cmd_count = 0;
    char line[4096];
    int in_vapor = 0;

    // ПРОХОД 1: Сбор команд и меток
    while (fgets(line, sizeof(line), file)) {
        if (strstr(line, "[VAPOR_LAYER]")) { in_vapor = 1; continue; }
        if (strstr(line, "[LIQUID_LAYER]")) { in_vapor = 0; break; }
        if (!in_vapor) continue;

        char* start = strchr(line, '§');
        while (start != NULL) {
            char* end = strchr(start + 1, '§');
            if (!end) break;
            
            *end = '\0';
            char* cmd = start + 1;
            
            commands[cmd_count] = strdup(cmd);
            
            // Если это метка, запоминаем её индекс
            if (strncmp(cmd, "LABEL::", 7) == 0) {
                strncpy(label_names[label_count], cmd + 7, 49);
                label_indexes[label_count] = cmd_count;
                label_count++;
            }
            
            cmd_count++;
            start = strchr(end + 1, '§');
        }
    }
    fclose(file);

    printf("[Drink VM] Starting execution...\n");

    // ПРОХОД 2: Выполнение
    int pc = 0; // Program Counter
    while (pc < cmd_count) {
        char* cmd = commands[pc];

        if (strncmp(cmd, "DROP_POWDER::", 13) == 0) {
            push_int(atoi(cmd + 13));
        } 
        else if (strncmp(cmd, "DROP_STRING::", 13) == 0) {
            push_str(cmd + 13);
        } 
        else if (strncmp(cmd, "VESSEL::", 8) == 0) {
            set_var(cmd + 8, pop());
        } 
        else if (strncmp(cmd, "SIP::", 5) == 0) {
            Value v = get_var(cmd + 5);
            if (v.is_string) push_str(v.str);
            else push_int(v.num);
        } 
        else if (strcmp(cmd, "SCAN_INPUT") == 0) {
            char buf[256];
            printf(">>> ");
            if (fgets(buf, sizeof(buf), stdin)) {
                buf[strcspn(buf, "\n")] = 0;
                push_str(buf);
            }
        }
        else if (strcmp(cmd, "CONVERT_NUM") == 0) {
            Value v = pop();
            push_int(v.is_string ? atoi(v.str) : v.num);
        }
        else if (strcmp(cmd, "CONVERT_STR") == 0) {
            Value v = pop();
            if (v.is_string) push_str(v.str);
            else {
                char buf[64];
                sprintf(buf, "%d", v.num);
                push_str(buf);
            }
        }
        else if (strcmp(cmd, "FUSE") == 0) { // Сложение (+)
            Value b = pop(); Value a = pop();
            if (a.is_string || b.is_string) {
                char r[512];
                if (a.is_string) strcpy(r, a.str); else sprintf(r, "%d", a.num);
                if (b.is_string) strcat(r, b.str); else sprintf(r + strlen(r), "%d", b.num);
                push_str(r);
            } else {
                push_int(a.num + b.num);
            }
        } 
        else if (strcmp(cmd, "EVAPORATE") == 0) { // Вычитание (-)
            Value b = pop(); Value a = pop();
            push_int(a.num - b.num);
        } 
        else if (strcmp(cmd, "MULTIPLY") == 0) { // Умножение (*)
            Value b = pop(); Value a = pop();
            push_int(a.num * b.num);
        } 
        else if (strcmp(cmd, "FILTER") == 0) { // Деление (/)
            Value b = pop(); Value a = pop();
            if (b.num != 0) push_int(a.num / b.num);
            else push_int(0);
        } 
        else if (strcmp(cmd, "COMPARE_EQ") == 0) {
            Value b = pop(); Value a = pop();
            push_int((a.is_string && b.is_string) ? strcmp(a.str, b.str) == 0 : a.num == b.num);
        }
        else if (strcmp(cmd, "COMPARE_NEQ") == 0) {
            Value b = pop(); Value a = pop();
            push_int((a.is_string && b.is_string) ? strcmp(a.str, b.str) != 0 : a.num != b.num);
        }
        else if (strcmp(cmd, "COMPARE_LT") == 0) {
            Value b = pop(); Value a = pop(); push_int(a.num < b.num);
        }
        else if (strcmp(cmd, "COMPARE_GT") == 0) {
            Value b = pop(); Value a = pop(); push_int(a.num > b.num);
        }
        else if (strcmp(cmd, "LOGIC_AND") == 0) {
            Value b = pop(); Value a = pop(); push_int((a.num != 0 && b.num != 0));
        }
        else if (strcmp(cmd, "LOGIC_OR") == 0) {
            Value b = pop(); Value a = pop(); push_int((a.num != 0 || b.num != 0));
        }
        else if (strcmp(cmd, "NEGATE") == 0) {
            Value a = pop(); push_int(-a.num);
        }
        else if (strcmp(cmd, "NOT") == 0) {
            Value a = pop(); push_int(a.num == 0);
        }
        else if (strcmp(cmd, "EXHALE_VAPOR") == 0) { // Вывод
            Value v = pop();
            if (v.is_string) printf("%s\n", v.str);
            else printf("%d\n", v.num);
        }
        else if (strncmp(cmd, "JUMP::", 6) == 0) { // Безусловный прыжок
            int target = get_label_index(cmd + 6);
            if (target != -1) { pc = target; continue; }
        } 
        else if (strncmp(cmd, "JUMP_IF_FALSE::", 15) == 0) { // Прыжок, если ложь
            Value cond = pop();
            if (cond.num == 0) {
                int target = get_label_index(cmd + 15);
                if (target != -1) { pc = target; continue; }
            }
        }
        else if (strncmp(cmd, "LABEL::", 7) == 0) {
            // Просто пропускаем, мы уже собрали метки
        }
        else if (strcmp(cmd, "QUENCH_THIRST") == 0) {
            break;
        }
        
        pc++;
    }

    printf("[Drink VM] Program finished.\n");
    return 0;
}