
import sqlite3
import os
from calc import materials_cost_unit

DB_PATH = 'test_calc.db'

def test_cost_calculation():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Setup Schema
    cur.execute("CREATE TABLE materias_primas (id INTEGER PRIMARY KEY, nome TEXT, estoque_atual REAL, custo_medio REAL)")
    cur.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY, nome TEXT)")
    cur.execute("CREATE TABLE produto_composicao (id INTEGER PRIMARY KEY, produto_id INTEGER, materia_id INTEGER, quantidade_por_unidade REAL)")
    
    # Data
    cur.execute("INSERT INTO materias_primas (nome, custo_medio) VALUES ('MDF 6mm', 50.0)")
    mdf_id = cur.lastrowid
    
    cur.execute("INSERT INTO produtos (nome) VALUES ('Produto Teste')")
    prod_id = cur.lastrowid
    
    # Composition: 0.166666666 (1/6) of MDF per product
    qtd_per_unit = 1.0 / 6.0
    cur.execute("INSERT INTO produto_composicao (produto_id, materia_id, quantidade_por_unidade) VALUES (?, ?, ?)", (prod_id, mdf_id, qtd_per_unit))
    conn.commit()
    
    # Calculate Cost
    cost = materials_cost_unit(conn, prod_id)
    print(f"Cost per unit: {cost}")
    
    expected_cost = 50.0 * qtd_per_unit # 8.333...
    print(f"Expected cost: {expected_cost}")
    
    if abs(cost - expected_cost) < 0.01:
        print("PASS: Cost calculation is correct.")
    else:
        print(f"FAIL: Cost calculation is wrong. Got {cost}, expected {expected_cost}")
        # If the bug was present, cost would be 50 / 0.1666 = 300
        if abs(cost - 300.0) < 0.1:
            print("DIAGNOSIS: Still using the old division logic for MDF.")

    conn.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

if __name__ == "__main__":
    test_cost_calculation()
