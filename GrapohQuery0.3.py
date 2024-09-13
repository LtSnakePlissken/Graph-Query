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


# Ask the user to select or add a subgraph
def get_subgraph(data):
    if data['subgraphs']:
        choices = list(data['subgraphs'].keys()) + ['New Subgraph']

        question = [
            inquirer.List('subgraph', message="Choose a subgraph", choices=choices)
        ]
        answer = inquirer.prompt(question)

        if answer['subgraph'] == 'New Subgraph':
            name = input("Enter a name for the new subgraph: ").strip()
            link = input("Enter the GraphQL endpoint URL: ").strip()
            data['subgraphs'][name] = link
            save_data(data)
            return link
        else:
            return data['subgraphs'][answer['subgraph']]
    else:
        print("No subgraphs available. Please add a new one.")
        name = input("Enter a name for the new subgraph: ").strip()
        link = input("Enter the GraphQL endpoint URL: ").strip()
        data['subgraphs'][name] = link
        save_data(data)
        return link


# Ask the user to select or add an address
def get_address(data):
    if data['addresses']:
        choices = [f"{name} ({address})" for name, address in data['addresses'].items()] + ['New Address']

        question = [
            inquirer.List('address', message="Choose an address", choices=choices)
        ]
        answer = inquirer.prompt(question)

        if answer['address'] == 'New Address':
            name = input("Enter a name for the new address: ").strip()
            address = input("Enter the Ethereum address: ").strip()
            data['addresses'][name] = address
            save_data(data)
            return address
        else:
            # Extract the actual Ethereum address from the selection
            selected_address = answer['address'].split('(')[-1].strip(')')
            return selected_address
    else:
        print("No addresses available. Please add a new one.")
        name = input("Enter a name for the new address: ").strip()
        address = input("Enter the Ethereum address: ").strip()
        data['addresses'][name] = address
        save_data(data)
        return address


# The main function that runs the query
def run_query():
    data = load_data()

    # Get the subgraph link
    subgraph_url = get_subgraph(data)

    # Get the Ethereum address
    address = get_address(data)

    # Define the GraphQL query with the user's address
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

    # Send the request to the subgraph
    response = requests.post(subgraph_url, json={'query': query})

    # Check if the request was successful
    if response.status_code == 200:
        response_json = response.json()

        if 'errors' in response_json:
            print("GraphQL query errors:", json.dumps(response_json['errors'], indent=2))
        elif 'data' in response_json:
            data = response_json['data']

            # Process the mints and burns data
            mints = data['mints']
            burns = data['burns']
            pairs = data['pairs']

            # Dictionary to store the net LP token amounts per pair
            address_summary = {}
            # Dictionary to accumulate token totals across all pairs
            token_totals = {}

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
                    net_liquidity = address_summary[pair_id]['liquidity_minted'] - address_summary[pair_id][
                        'liquidity_burned']

                    # Only display pairs where the wallet has a positive net liquidity
                    if net_liquidity > 0 and total_supply > 0:
                        # Proportion of the pool owned by the user
                        proportion = net_liquidity / total_supply

                        # Calculate the user's share of token0 and token1
                        user_token0 = proportion * reserve0
                        user_token1 = proportion * reserve1

                        token0_symbol = pair['token0']['symbol']
                        token1_symbol = pair['token1']['symbol']

                        # Add to token totals
                        if token0_symbol not in token_totals:
                            token_totals[token0_symbol] = 0
                        if token1_symbol not in token_totals:
                            token_totals[token1_symbol] = 0

                        token_totals[token0_symbol] += user_token0
                        token_totals[token1_symbol] += user_token1

                        print(f"Pair {pair_id}: {token0_symbol} = {user_token0}, {token1_symbol} = {user_token1}")

            # Display the total amounts of each token across all pairs
            print("\nTotal amounts across all pairs:")
            for token, total in token_totals.items():
                print(f"{token}: {total}")

    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        print(f"Response content: {response.text}")


# Run the program
run_query()
