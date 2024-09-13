import requests
import json

# Define the GraphQL endpoint (replace with your subgraph's GraphQL URL)
graphql_url = "http://162.244.80.145:8000/subgraphs/name/elkfinance-q/"

# Define the GraphQL query
query = """
{
  mints(where: { to: "0xB2312009bEd27B5962169586129fF55b185129e2" }) {
    id
    liquidity
    pair {
      id
      token0 {
        symbol
      }
      token1 {
        symbol
      }
    }
    transaction {
      blockNumber
      timestamp
    }
  }
  burns(where: { sender: "0xB2312009bEd27B5962169586129fF55b185129e2" }) {
    id
    liquidity
    pair {
      id
      token0 {
        symbol
      }
      token1 {
        symbol
      }
    }
    transaction {
      blockNumber
      timestamp
    }
  }
  pairs {
    id
    token0 {
      symbol
    }
    token1 {
      symbol
    }
    reserve0
    reserve1
    totalSupply
  }
}
"""

# Send the request to the subgraph
response = requests.post(graphql_url, json={'query': query})

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

                    print(
                        f"Pair {pair_id}: {pair['token0']['symbol']} = {user_token0}, {pair['token1']['symbol']} = {user_token1}")
    else:
        print("Unexpected response format:", response_json)
else:
    print(f"Failed to fetch data. Status code: {response.status_code}")
    print(f"Response content: {response.text}")
