import json
import requests
import os
import inquirer

# File to store subgraph links and addresses
storage_file = "subgraph_data.json"


# Load or initialize subgraph data from the file
def load_data():
    if os.path.exists(storage_file):
        with open(storage_file, 'r') as f:
            return json.load(f)
    else:
        return {'subgraphs': {}, 'addresses': {}}


# Save subgraph data to the file
def save_data(data):
    with open(storage_file, 'w') as f:
        json.dump(data, f, indent=2)


# Ask the user to select or add subgraphs
def get_subgraphs(data):
    if data['subgraphs']:
        choices = list(data['subgraphs'].keys()) + ['New Subgraph']

        questions = [
            inquirer.Checkbox('subgraphs', message="Choose subgraphs (chains)", choices=choices)
        ]
        answers = inquirer.prompt(questions)

        selected_subgraphs = []
        if 'New Subgraph' in answers['subgraphs']:
            while True:
                name = input("Enter a name for the new subgraph (or type 'done' to finish): ").strip()
                if name.lower() == 'done':
                    break
                link = input("Enter the GraphQL endpoint URL: ").strip()
                data['subgraphs'][name] = link
                save_data(data)
                selected_subgraphs.append((name, link))
        else:
            selected_subgraphs = [(name, data['subgraphs'][name]) for name in answers['subgraphs'] if
                                  name != 'New Subgraph']

        return selected_subgraphs
    else:
        print("No subgraphs available. Please add a new one.")
        name = input("Enter a name for the new subgraph: ").strip()
        link = input("Enter the GraphQL endpoint URL: ").strip()
        data['subgraphs'][name] = link
        save_data(data)
        return [(name, link)]


# Ask the user to select or add addresses for each subgraph
def get_addresses(data, subgraph_name):
    if data['addresses']:
        choices = [f"{name} ({address})" for name, address in data['addresses'].items()] + ['New Address']

        question = [
            inquirer.Checkbox('addresses', message=f"Choose addresses for {subgraph_name}", choices=choices)
        ]
        answer = inquirer.prompt(question)

        selected_addresses = []
        if 'New Address' in answer['addresses']:
            while True:
                name = input("Enter a name for the new address (or type 'done' to finish): ").strip()
                if name.lower() == 'done':
                    break
                address = input("Enter the Ethereum address: ").strip()
                data['addresses'][name] = address
                save_data(data)
                selected_addresses.append((name, address))
        else:
            selected_addresses = [(name.split(' (')[0], name.split('(')[-1].strip(')')) for name in answer['addresses']
                                  if name != 'New Address']

        return selected_addresses
    else:
        print(f"No addresses available. Please add a new one for {subgraph_name}.")
        name = input("Enter a name for the new address: ").strip()
        address = input("Enter the Ethereum address: ").strip()
        data['addresses'][name] = address
        save_data(data)
        return [(name, address)]


# Perform GraphQL query for each chain and address
def query_chain(subgraph_url, address):
    query = f"""
    {{
      mints(where: {{ to: "{address}" }}) {{
        id
        liquidity
        pair {{
          id
          token0 {{
            symbol
          }}
          token1 {{
            symbol
          }}
        }}
        transaction {{
          blockNumber
          timestamp
        }}
      }}
      burns(where: {{ sender: "{address}" }}) {{
        id
        liquidity
        pair {{
          id
          token0 {{
            symbol
          }}
          token1 {{
            symbol
          }}
        }}
        transaction {{
          blockNumber
          timestamp
        }}
      }}
      pairs {{
        id
        token0 {{
          symbol
        }}
        token1 {{
          symbol
        }}
        reserve0
        reserve1
        totalSupply
      }}
    }}
    """

    response = requests.post(subgraph_url, json={'query': query})

    if response.status_code == 200:
        return response.json().get('data')
    else:
        print(f"Failed to fetch data for {address}. Status code: {response.status_code}")
        return None


# Process data for a single address and chain
def process_data(data, address, address_totals):
    mints = data['mints']
    burns = data['burns']
    pairs = data['pairs']

    # Dictionary to store the net LP token amounts per pair
    address_summary = {}

    # Process mints
    for mint in mints:
        pair_id = mint['pair']['id']
        liquidity = float(mint['liquidity'])

        if pair_id not in address_summary:
            address_summary[pair_id] = {'liquidity_minted': 0, 'liquidity_burned': 0}

        address_summary[pair_id]['liquidity_minted'] += liquidity

    # Process burns
    for burn in burns:
        pair_id = burn['pair']['id']
        liquidity = float(burn['liquidity'])

        if pair_id not in address_summary:
            address_summary[pair_id] = {'liquidity_minted': 0, 'liquidity_burned': 0}

        address_summary[pair_id]['liquidity_burned'] += liquidity

    # Calculate the current amount of tokens based on the LP balance and pair reserves
    for pair in pairs:
        pair_id = pair['id']
        total_supply = float(pair['totalSupply'])
        reserve0 = float(pair['reserve0'])
        reserve1 = float(pair['reserve1'])

        if pair_id in address_summary:
            net_liquidity = address_summary[pair_id]['liquidity_minted'] - address_summary[pair_id]['liquidity_burned']

            if net_liquidity > 0 and total_supply > 0:
                # Proportion of the pool owned by the user
                proportion = net_liquidity / total_supply

                # Calculate the user's share of token0 and token1
                user_token0 = proportion * reserve0
                user_token1 = proportion * reserve1

                token0_symbol = pair['token0']['symbol']
                token1_symbol = pair['token1']['symbol']

                # Add to address totals
                if token0_symbol not in address_totals:
                    address_totals[token0_symbol] = 0
                if token1_symbol not in address_totals:
                    address_totals[token1_symbol] = 0

                address_totals[token0_symbol] += user_token0
                address_totals[token1_symbol] += user_token1


# Main function
def run_query():
    data = load_data()

    # Select multiple subgraphs (chains)
    selected_subgraphs = get_subgraphs(data)

    grand_totals = {}  # Grand totals across all chains and addresses

    for subgraph_name, subgraph_url in selected_subgraphs:
        print(f"\n--- Processing chain: {subgraph_name} ---")

        # Select multiple addresses for each subgraph
        selected_addresses = get_addresses(data, subgraph_name)

        for address_name, address in selected_addresses:
            print(f"\n  Address: {address_name} ({address})")
            address_totals = {}  # Totals for each address

            # Query the chain for this address
            query_result = query_chain(subgraph_url, address)
            if query_result:
                # Process the data for this address
                process_data(query_result, address, address_totals)

                # Display totals for this address
                print(f"  Totals for {address_name}:")
                for token, total in address_totals.items():
                    print(f"    {token}: {total}")

                # Add to grand totals
                for token, total in address_totals.items():
                    if token not in grand_totals:
                        grand_totals[token] = 0
                    grand_totals[token] += total

    # Display grand totals across all chains and addresses
    print("\n--- Grand Totals across all chains and addresses ---")
    for token, total in grand_totals.items():
        print(f"{token}: {total}")


# Run the program
run_query()
