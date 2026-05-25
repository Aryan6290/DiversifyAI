import os
import sys
import argparse
from dotenv import load_dotenv
from analyzer import PortfolioAnalyzer

# ANSI escape codes for beautiful terminal colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(title: str):
    print(f"\n{BLUE}{BOLD}{'='*60}\n{title:^60}\n{'='*60}{RESET}")

def main():
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="GenAI Portfolio Diversification Analyzer"
    )
    parser.add_argument(
        "csv_path",
        help="Path to the portfolio CSV file"
    )
    parser.add_argument(
        "--provider",
        default="gemini",
        choices=["gemini", "openai", "anthropic"],
        help="LLM Provider to use (default: gemini)"
    )
    parser.add_argument(
        "--key",
        help="Custom API key for the chosen provider (optional)"
    )
    args = parser.parse_args()

    print_header("PORTFOLIO DIVERSIFICATION ANALYZER")

    provider_name = args.provider.lower().strip()

    # Determine key and provide helpful CLI feedback
    api_key = args.key
    if not api_key:
        env_var_name = f"{provider_name.upper()}_API_KEY"
        api_key = os.getenv(env_var_name)
        if not api_key:
            print(f"{YELLOW}{BOLD}⚠️  WARNING:{RESET} {env_var_name} is not set in your environment or .env file.")
            print(f"The analyzer will calculate local statistics but will NOT be able to invoke the AI advisory report.")
            print(f"To unlock GenAI capabilities, provide a key via --key or add to `.env`:\n  {BOLD}{env_var_name}=your_api_key{RESET}\n")

    try:
        # Initialize analyzer
        analyzer = PortfolioAnalyzer(api_key=api_key, provider=provider_name)

        # Load CSV
        print(f"{BLUE}📂 Loading portfolio from: {RESET}{args.csv_path}...")
        portfolio_df = analyzer.load_portfolio(args.csv_path)
        print(f"{GREEN}✓ Portfolio loaded successfully!{RESET} ({len(portfolio_df)} assets found)\n")

        # Local analysis and calculations
        print(f"{BLUE}📊 Calculating asset and sector allocations...{RESET}")
        allocations = analyzer.calculate_allocations(portfolio_df)

        # Display raw allocations locally
        print(f"\n{BOLD}Total Portfolio Value:{RESET} ${allocations['total_value']:,.2f} USD\n")
        
        print(f"{BOLD}Asset Type Breakdown:{RESET}")
        asset_breakdown = allocations["asset_type_breakdown"].copy()
        asset_breakdown["Current Value"] = asset_breakdown["Current Value"].apply(lambda v: f"${v:,.2f}")
        asset_breakdown["Percentage"] = asset_breakdown["Percentage"].apply(lambda p: f"{p:.2f}%")
        print(asset_breakdown.to_markdown(index=False))
        print()

        print(f"{BOLD}Sector Breakdown:{RESET}")
        sector_breakdown = allocations["sector_breakdown"].copy()
        sector_breakdown["Current Value"] = sector_breakdown["Current Value"].apply(lambda v: f"${v:,.2f}")
        sector_breakdown["Percentage"] = sector_breakdown["Percentage"].apply(lambda p: f"{p:.2f}%")
        print(sector_breakdown.to_markdown(index=False))
        print()

        # GenAI analysis report
        print_header("GENAI DIVERSIFICATION ADVISORY REPORT")
        print(f"{BLUE}🤖 Requesting analysis from {BOLD}{provider_name.upper()}{RESET}{BLUE}...{RESET}")
        
        report = analyzer.generate_diversification_report(portfolio_df, allocations)
        
        print(f"\n{GREEN}{BOLD}Report generated!{RESET}\n")
        print(report)
        print(f"\n{BLUE}{'='*60}{RESET}\n")

    except FileNotFoundError as e:
        print(f"\n{RED}{BOLD}❌ Error:{RESET} {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n{RED}{BOLD}❌ CSV Format Error:{RESET} {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}{BOLD}❌ Unexpected Error:{RESET} {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
