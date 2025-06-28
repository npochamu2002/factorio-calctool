import json
import tkinter as tk
from tkinter import ttk, messagebox
import os

DATA_JSON_PATH = "data.json"
MACHINE_JSON_PATH = "machine.json"

def load_json_file(path):
    if not os.path.exists(path):
        messagebox.showerror("エラー", f"{path} が見つかりません。")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

data_json = load_json_file(DATA_JSON_PATH)
machine_json = load_json_file(MACHINE_JSON_PATH)

if data_json is None or machine_json is None:
    exit(1)

root = tk.Tk()
root.title("Factorio生産計算ツール")
root.geometry("1000x800")  # 高さ少し増やす

default_font = ("Meiryo", 11)
header_font = ("Meiryo", 11, "bold")

search_var = tk.StringVar()
recipe_var = tk.StringVar()
machine_var = tk.StringVar()
amount_var = tk.StringVar(value="1")

all_recipes = list(data_json["recipes"].keys())
display_recipe_names = [data_json["recipes"][r]["translated_name"] for r in all_recipes]
translated_to_key = {data_json["recipes"][r]["translated_name"]: r for r in all_recipes}

current_machine_choices = {}
manual_machine_selection = {}

def on_search_var_change(*args):
    keyword = search_var.get().lower()
    filtered = [data_json["recipes"][r]["translated_name"] for r in all_recipes if keyword in data_json["recipes"][r]["translated_name"].lower()]
    update_recipe_combo(filtered)

def update_recipe_combo(recipe_list):
    recipe_combo['values'] = recipe_list
    if recipe_list:
        recipe_combo.current(0)
        on_recipe_selected()
    else:
        recipe_var.set("")
        clear_machine_combo()

def on_recipe_selected(event=None):
    selected_trans = recipe_var.get()
    if not selected_trans:
        clear_machine_combo()
        return
    rkey = translated_to_key.get(selected_trans)
    if not rkey:
        clear_machine_combo()
        return
    category = data_json["recipes"][rkey]["category"]
    machines = machine_json.get(category, {})
    update_machine_combo(list(machines.keys()))

def update_machine_combo(machines):
    global current_machine_choices
    current_machine_choices = {}
    rkey = translated_to_key.get(recipe_var.get())
    if not rkey:
        clear_machine_combo()
        return
    category = data_json["recipes"][rkey]["category"]
    machines_info = machine_json.get(category, {})
    for m in machines:
        info = machines_info.get(m)
        if info is not None and "speed" in info:
            current_machine_choices[m] = info["speed"]
    machine_combo['values'] = list(current_machine_choices.keys())
    if current_machine_choices:
        machine_combo.current(0)
        machine_var.set(machine_combo.get())
    else:
        machine_var.set("")

def clear_machine_combo():
    machine_combo['values'] = []
    machine_var.set("")
    global current_machine_choices
    current_machine_choices = {}

def find_recipe_for_item(item_name):
    for rkey, rdata in data_json["recipes"].items():
        if "products" in rdata:
            for product in rdata["products"]:
                if product.get("type") == "item" and product.get("name") == item_name:
                    return rkey
        elif "result" in rdata and rdata.get("result") == item_name:
            return rkey
        elif "results" in rdata:
            for res in rdata["results"]:
                if res.get("type") == "item" and res.get("name") == item_name:
                    return rkey
    return None

def find_best_machine(category):
    machines = machine_json.get(category, {})
    if machines:
        # 最高速度の設備名を返す
        return max(machines.items(), key=lambda x: x[1].get("speed", 0))[0]
    return "なし"

def depth_to_color(depth):
    base = 240  # 青色ベース
    value = max(255 - depth * 20, 200)
    return f"#{value:02x}{value:02x}{255:02x}"

def get_expanded_items(tree):
    expanded = []
    def recurse(item):
        if tree.item(item, "open"):
            expanded.append(item)
            for child in tree.get_children(item):
                recurse(child)
    for root_item in tree.get_children():
        recurse(root_item)
    return expanded

def restore_expanded_items(tree, expanded_items):
    for item in expanded_items:
        if tree.exists(item):
            tree.item(item, open=True)

def add_ingredient_tree(tree, parent, ingredient_name, amount, multiplier=1.0, depth=1):
    total_amount = amount * multiplier
    recipe_key = find_recipe_for_item(ingredient_name)

    tag = f"depth{depth}"
    bg_color = depth_to_color(depth)
    if not tree.tag_has(tag):
        tree.tag_configure(tag, background=bg_color)

    node_id = ingredient_name + f"_{parent}_{depth}"  # ユニークID化（親・深さ含む）

    # 重複防止のため既存削除
    if tree.exists(node_id):
        tree.delete(node_id)

    if recipe_key:
        recipe = data_json["recipes"][recipe_key]
        category = recipe.get("category", "crafting")

        machine = manual_machine_selection.get(ingredient_name)
        if not machine:
            machine = find_best_machine(category)
        machine_speed = machine_json.get(category, {}).get(machine, {}).get("speed", 1)
        energy = recipe.get("energy", 1)
        prod_per_min = (machine_speed / energy) * 60 if energy != 0 else 0
        machines_needed = total_amount / prod_per_min if prod_per_min else 0
        text = f"{ingredient_name} ({machines_needed:.2f}台)"

        tree.insert(parent, "end", iid=node_id, values=(text, f"{total_amount:.2f}", machine), tags=(ingredient_name, tag))

        for ing in recipe.get("ingredients", []):
            if ing["type"] == "item":
                add_ingredient_tree(tree, node_id, ing["name"], ing["amount"], multiplier=total_amount, depth=depth + 1)
    else:
        tree.insert(parent, "end", iid=node_id, values=(ingredient_name, f"{total_amount:.2f}", "原料"), tags=(ingredient_name, tag))

def change_machine_for_selected():
    selected = result_tree.selection()
    if not selected:
        return
    item_id = selected[0]
    tags = result_tree.item(item_id, "tags")
    if not tags:
        return
    item_name = tags[0]
    recipe_key = find_recipe_for_item(item_name)
    if not recipe_key:
        messagebox.showinfo("情報", "レシピが見つかりません。")
        return
    category = data_json["recipes"][recipe_key]["category"]
    machines = machine_json.get(category, {})
    machine_names = list(machines.keys())

    def set_machine():
        selected_machine = combo.get()
        if selected_machine in machines:
            manual_machine_selection[item_name] = selected_machine
            top.destroy()
            calculate()

    top = tk.Toplevel(root)
    top.title(f"{item_name} の設備選択")
    tk.Label(top, text=f"{item_name} に使用する設備を選択してください:", font=default_font).pack(padx=10, pady=10)
    combo = ttk.Combobox(top, values=machine_names, state="readonly", font=default_font)
    combo.pack(padx=10, pady=5)
    if machine_names:
        combo.current(0)
    tk.Button(top, text="決定", command=set_machine, font=default_font).pack(padx=10, pady=10)

def calculate():
    expanded_before = get_expanded_items(result_tree)

    selected_trans = recipe_var.get()
    if not selected_trans:
        messagebox.showwarning("エラー", "レシピを選択してください。")
        return
    rkey = translated_to_key.get(selected_trans)
    recipe = data_json["recipes"].get(rkey)
    if not recipe:
        messagebox.showerror("エラー", "レシピ情報がありません。")
        return
    try:
        demand_per_min = float(amount_var.get())
        if demand_per_min <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("エラー", "毎分要求個数は正の数を入力してください。")
        return

    machine_name = machine_var.get()
    if machine_name not in current_machine_choices:
        messagebox.showerror("エラー", "設備を正しく選択してください。")
        return
    machine_speed = current_machine_choices[machine_name]
    energy = recipe.get("energy", 1)
    production_per_min = (machine_speed / energy) * 60 if energy != 0 else 0
    machines_needed = demand_per_min / production_per_min if production_per_min else 0

    result_tree.delete(*result_tree.get_children())

    root_text = f"{selected_trans} (設備: {machine_name}, 要求: {demand_per_min}個/分, 台数: {machines_needed:.2f}台)"
    root_id = selected_trans + "_root"
    if result_tree.exists(root_id):
        result_tree.delete(root_id)
    result_tree.insert("", "end", iid=root_id, values=(root_text, f"{demand_per_min:.2f}", machine_name), tags=(root_id, "depth0"))

    for ing in recipe.get("ingredients", []):
        if ing["type"] == "item":
            add_ingredient_tree(result_tree, root_id, ing["name"], ing["amount"], multiplier=demand_per_min, depth=1)

    restore_expanded_items(result_tree, expanded_before)

    # --- ここからデバッグ表示 ---
    debug_text.delete("1.0", tk.END)

    debug_text.insert(tk.END, f"■ 計算詳細 ■\n")
    debug_text.insert(tk.END, f"選択レシピ: {selected_trans}\n")
    debug_text.insert(tk.END, f"設備: {machine_name}\n")
    debug_text.insert(tk.END, f"設備速度: {machine_speed}\n")
    debug_text.insert(tk.END, f"レシピエネルギー（生産時間）: {energy} 秒\n")
    debug_text.insert(tk.END, f"要求個数: {demand_per_min} 個/分\n")
    debug_text.insert(tk.END, f"生産能力（個/分）: {production_per_min:.2f}\n")
    debug_text.insert(tk.END, f"必要台数: {machines_needed:.2f} 台\n\n")

    def debug_add_ingredient(item_name, amount, multiplier, depth=1):
        recipe_key = find_recipe_for_item(item_name)
        total_amount = amount * multiplier
        if not recipe_key:
            debug_text.insert(tk.END, f"{'  ' * depth}{item_name} (原料) 必要数: {total_amount:.2f}\n")
            return
        recipe = data_json["recipes"][recipe_key]
        category = recipe.get("category", "crafting")
        machine = manual_machine_selection.get(item_name)
        if not machine:
            machine = find_best_machine(category)
        speed = machine_json.get(category, {}).get(machine, {}).get("speed", 1)
        energy = recipe.get("energy", 1)
        prod_per_min = (speed / energy) * 60 if energy != 0 else 0
        machines = total_amount / prod_per_min if prod_per_min else 0
        debug_text.insert(tk.END, f"{'  ' * depth}{item_name} (設備:{machine}) 必要数: {total_amount:.2f} 台数: {machines:.2f}\n")
        for ing in recipe.get("ingredients", []):
            if ing["type"] == "item":
                debug_add_ingredient(ing["name"], ing["amount"], total_amount, depth + 1)

    for ing in recipe.get("ingredients", []):
        if ing["type"] == "item":
            debug_add_ingredient(ing["name"], ing["amount"], demand_per_min, 1)

search_var.trace_add("write", on_search_var_change)

# --- GUI構築 ---

# 検索とレシピ選択
frame_top = tk.Frame(root)
frame_top.pack(padx=10, pady=10, fill="x")

tk.Label(frame_top, text="レシピ検索:", font=default_font).pack(side="left")
search_entry = tk.Entry(frame_top, textvariable=search_var, font=default_font, width=30)
search_entry.pack(side="left", padx=5)

tk.Label(frame_top, text="レシピ選択:", font=default_font).pack(side="left", padx=(20, 5))
recipe_combo = ttk.Combobox(frame_top, textvariable=recipe_var, font=default_font, width=30, state="readonly")
recipe_combo.pack(side="left")
recipe_combo.bind("<<ComboboxSelected>>", on_recipe_selected)

# 設備選択・要求数
frame_middle = tk.Frame(root)
frame_middle.pack(padx=10, pady=5, fill="x")

tk.Label(frame_middle, text="設備選択:", font=default_font).pack(side="left")
machine_combo = ttk.Combobox(frame_middle, textvariable=machine_var, font=default_font, width=20, state="readonly")
machine_combo.pack(side="left", padx=5)

tk.Label(frame_middle, text="毎分要求個数:", font=default_font).pack(side="left", padx=(20,5))
amount_entry = tk.Entry(frame_middle, textvariable=amount_var, font=default_font, width=10)
amount_entry.pack(side="left")

btn_calc = tk.Button(frame_middle, text="計算", font=default_font, command=calculate)
btn_calc.pack(side="left", padx=20)

btn_change_machine = tk.Button(frame_middle, text="選択素材の設備変更", font=default_font, command=change_machine_for_selected)
btn_change_machine.pack(side="left")

# 結果表示Treeview
frame_tree = tk.Frame(root)
frame_tree.pack(padx=10, pady=10, fill="both", expand=True)

columns = ("説明", "必要数", "設備")
result_tree = ttk.Treeview(frame_tree, columns=columns, show="tree headings")
result_tree.heading("#0", text="素材")
result_tree.heading("説明", text="説明")
result_tree.heading("必要数", text="必要数")
result_tree.heading("設備", text="設備")
result_tree.column("#0", width=200)
result_tree.column("説明", width=400)
result_tree.column("必要数", width=100, anchor="e")
result_tree.column("設備", width=120)

result_tree.pack(fill="both", expand=True)

# デバッグ用テキスト
frame_debug = tk.Frame(root)
frame_debug.pack(padx=10, pady=5, fill="both", expand=False)

tk.Label(frame_debug, text="計算詳細（デバッグ用）:", font=header_font).pack(anchor="w")
debug_text = tk.Text(frame_debug, height=12, font=("Consolas", 10))
debug_text.pack(fill="both", expand=True)

# 初期化
update_recipe_combo(display_recipe_names)

root.mainloop()
