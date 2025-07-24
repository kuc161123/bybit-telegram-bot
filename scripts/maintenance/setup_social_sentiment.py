#!/usr/bin/env python3
"""
Social Media Sentiment Analysis Setup Script
Helps configure API credentials and test the system
"""
import os
import sys
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def print_banner():
    """Print setup banner"""
    print("=" * 60)
    print("📱 Social Media Sentiment Analysis Setup")
    print("=" * 60)
    print()

def check_environment():
    """Check if .env file exists and suggest creation"""
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    if not env_file.exists():
        print("⚠️  No .env file found!")
        if env_example.exists():
            print("💡 Creating .env file from .env.example...")
            env_file.write_text(env_example.read_text())
            print("✅ .env file created. Please edit it with your API credentials.")
        else:
            print("❌ No .env.example file found. Please create .env manually.")
        return False
    else:
        print("✅ .env file found")
        return True

def show_configuration_help():
    """Show configuration help"""
    print("\n📋 Social Media Sentiment Analysis Configuration")
    print("-" * 50)
    
    # Import configuration module
    try:
        from social_media.config import print_configuration_help
        print_configuration_help()
    except ImportError as e:
        print(f"❌ Could not import configuration module: {e}")
        return False
    
    return True

async def test_system():
    """Test the social media sentiment system"""
    print("\n🧪 Testing Social Media Sentiment System")
    print("-" * 40)
    
    try:
        from social_media.integration import test_sentiment_system
        
        # Run system test
        test_results = await test_sentiment_system()
        
        print("\n📊 Test Results:")
        print(f"Overall Status: {test_results.get('overall_status', 'unknown')}")
        
        if test_results.get('error'):
            print(f"❌ Error: {test_results['error']}")
        
        # Show platform status
        enabled_platforms = test_results.get('enabled_platforms', [])
        if enabled_platforms:
            print(f"✅ Enabled Platforms: {', '.join(enabled_platforms)} ({len(enabled_platforms)}/5)")
        else:
            print("⚠️  No platforms enabled - configure API credentials")
        
        # Show cache test
        cache_test = test_results.get('cache_test', {})
        if cache_test:
            cache_working = cache_test.get('working', False)
            print(f"💾 Cache System: {'✅ Working' if cache_working else '❌ Failed'}")
        
        return test_results.get('overall_status') in ['excellent', 'good', 'fair', 'basic']
        
    except ImportError as e:
        print(f"❌ Could not import sentiment system: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def run_manual_collection():
    """Run a manual sentiment collection cycle"""
    print("\n🎯 Running Manual Sentiment Collection")
    print("-" * 40)
    
    try:
        from social_media.integration import trigger_sentiment_collection
        
        print("🔄 Starting collection cycle...")
        result = await trigger_sentiment_collection()
        
        if result.get('success'):
            print("✅ Collection completed successfully!")
            
            # Show results summary
            aggregated = result.get('aggregated_sentiment', {})
            if aggregated:
                sentiment = aggregated.get('overall_sentiment', 'UNKNOWN')
                score = aggregated.get('sentiment_score', 0)
                quality = aggregated.get('data_quality', 'unknown')
                
                print(f"📊 Overall Sentiment: {sentiment} ({score}/100)")
                print(f"🎯 Data Quality: {quality.title()}")
                
                # Show platform breakdown
                platform_sentiments = result.get('platform_sentiments', {})
                if platform_sentiments:
                    print("\n📱 Platform Breakdown:")
                    for platform, data in platform_sentiments.items():
                        platform_sentiment = data.get('sentiment', 'UNKNOWN')
                        platform_score = data.get('sentiment_score', 0)
                        items_count = data.get('items_analyzed', 0)
                        print(f"  {platform}: {platform_sentiment} ({platform_score}/100) - {items_count} items")
            
        else:
            error = result.get('error', 'Unknown error')
            print(f"❌ Collection failed: {error}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Could not import sentiment system: {e}")
        return False
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        return False

def show_api_instructions():
    """Show API setup instructions"""
    print("\n📚 API Setup Instructions")
    print("-" * 30)
    print()
    
    instructions = {
        "Reddit API": [
            "1. Go to https://www.reddit.com/prefs/apps",
            "2. Click 'Create App' or 'Create Another App'",
            "3. Choose 'script' application type",
            "4. Copy the client ID and secret",
            "5. Add to .env: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET"
        ],
        "Twitter API v2": [
            "1. Go to https://developer.twitter.com/en/portal/dashboard",
            "2. Create a new project/app",
            "3. Generate Bearer Token",
            "4. Add to .env: TWITTER_BEARER_TOKEN"
        ],
        "YouTube Data API v3": [
            "1. Go to https://console.developers.google.com/",
            "2. Create a new project or select existing",
            "3. Enable YouTube Data API v3",
            "4. Create credentials (API Key)",
            "5. Add to .env: YOUTUBE_API_KEY"
        ],
        "Discord Bot (Optional)": [
            "1. Go to https://discord.com/developers/applications",
            "2. Create a new application",
            "3. Go to Bot section and create bot",
            "4. Copy the bot token",
            "5. Add to .env: DISCORD_BOT_TOKEN"
        ]
    }
    
    for api_name, steps in instructions.items():
        print(f"🔗 {api_name}:")
        for step in steps:
            print(f"   {step}")
        print()

async def main():
    """Main setup function"""
    print_banner()
    
    # Check environment
    env_exists = check_environment()
    
    if not env_exists:
        print("\n⚠️  Please edit the .env file with your API credentials before continuing.")
        print("📚 Use --help to see API setup instructions.")
        return
    
    # Show configuration
    show_configuration_help()
    
    # Interactive menu
    while True:
        print("\n🔧 Setup Options:")
        print("1. Test system configuration")
        print("2. Run manual collection cycle")
        print("3. Show API setup instructions")
        print("4. Exit")
        
        choice = input("\nChoose an option (1-4): ").strip()
        
        if choice == "1":
            success = await test_system()
            if success:
                print("\n✅ System test passed!")
            else:
                print("\n⚠️  System test failed. Check configuration.")
        
        elif choice == "2":
            success = await run_manual_collection()
            if success:
                print("\n✅ Manual collection completed!")
            else:
                print("\n⚠️  Manual collection failed.")
        
        elif choice == "3":
            show_api_instructions()
        
        elif choice == "4":
            print("\n👋 Setup complete! Use 'python main.py' to start the bot.")
            break
        
        else:
            print("❌ Invalid choice. Please select 1-4.")

if __name__ == "__main__":
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print_banner()
            show_api_instructions()
            sys.exit(0)
    
    # Run the main setup
    asyncio.run(main())