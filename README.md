# TimekeeperV2

> **⚠️ TRANSPARENCY REPOSITORY**: This repository exists for transparency with our user community. The code is **NOT** intended for self-hosting or redistribution. See [License](#license) for details.

**TimekeeperV2** is an enterprise-grade Discord time tracking bot designed for businesses, RP servers, and communities requiring sophisticated time logging and productivity analytics.

This is the spiritual successor to the original Timekeeper bot (EOL'd 2025), rebuilt from the ground up with enterprise reliability patterns and advanced analytics.

---

## 🔗 Quick Links

- **Add to your server**: [timekeeper.404connernotfound.dev](https://timekeeper.404connernotfound.dev)
- **Documentation**: [docs.timekeeper.404connernotfound.dev](https://docs.timekeeper.404connernotfound.dev)
- **Support Server**: [discord.gg/timekeeper](https://discord.gg/timekeeper)

---

## ✨ Features

### Core Time Tracking

- **Clock In/Out System** with Discord role integration
- **Multi-Category Support** - Configurable per-server categories
- **Real-Time Session Tracking** with automatic role assignment
- **Persistent Dashboards** - Interactive, always-available control panels
- **Force Clockout** - Admin controls for session management

### Advanced Analytics

- **ML-Powered Productivity Scoring** - Machine learning models analyze work patterns
- **Predictive Analytics** - Forecast future productivity trends
- **Category Insights** - Detailed breakdowns with trend analysis
- **Streak Tracking** - Gamified consistency monitoring
- **Comparative Metrics** - See how you rank on your server

### Data & Export

- **Multi-Format Export** - CSV, PDF, and DOCX export options
- **Leaderboards** - Time-based filtering (all time, week, month)
- **Activity Logging** - Optional audit trail of all clock events
- **Comprehensive Stats** - User and server-wide analytics

### Enterprise Architecture

- **Redis-Based Storage** - High-performance data persistence
- **Multi-Layer Caching** - L1/L2/L3 cache hierarchy for speed
- **Circuit Breaker Pattern** - Graceful degradation under load
- **Batch Processing** - Optimized write operations
- **Health Monitoring** - Real-time system health checks
- **Rate Limiting** - Built-in protection against abuse

---

## 🏗️ Architecture

### Tech Stack

- **Runtime**: Python 3.12+ (discord.py 2.x)
- **Database**: Redis (primary data store)
- **Caching**: Multi-tier (TTL, LRU, LFU)
- **Analytics**: Custom ML models with sklearn-compatible API
- **Reliability**: Circuit breaker, batch processor, fallback storage

### Key Components

```
src/
├── Core/           # Bot runtime and initialization
├── Commands/       # Slash command handlers
│   ├── timecard.py       # Clock in/out/status
│   ├── admin.py          # Category & system management
│   ├── dashboard.py      # Interactive dashboards
│   ├── leaderboard.py    # Rankings & competitions
│   ├── predictions.py    # ML insights
│   └── export.py         # Data export
├── Utils/          # Business logic
│   ├── timekeeper.py     # Core tracking engine
│   ├── permissions.py    # Permission system
│   └── activity_integration.py
└── Data/           # Persistent storage configs
```

---

## 📊 Command Reference

### User Commands

- `/clockin <category>` - Start tracking time
- `/clockout` - Stop tracking and save session
- `/status` - View your current status and stats
- `/dashboard [personal:bool]` - Open interactive dashboard
- `/leaderboard [category] [timeframe]` - View server rankings
- `/insights [user]` - Advanced productivity analytics
- `/export <format> [user]` - Export your data

### Admin Commands

- `/admin categories` - Manage time tracking categories
- `/admin system` - View system health and metrics
- `/config` - Configure server settings and permissions
- `/activitylog` - Configure activity logging
- `/forceclockout <user>` - Force clock out a user

---

## 🎯 Key Features Explained

### Intelligent Category Management

Server administrators configure custom categories (work, meetings, development, etc.). The system:

- Validates categories server-side
- Provides smart suggestions for typos
- Tracks metadata (color, description, productivity weight)
- Archives categories with historical data

### Advanced Productivity Scoring

The analytics engine calculates productivity scores based on:

- **Consistency** - Regular work patterns
- **Balance** - Healthy work-life distribution
- **Time Patterns** - Working during optimal hours
- **Session Quality** - Optimal session lengths
- **Focus** - Fewer, longer sessions vs many short ones
- **Trend Analysis** - Improvement over time

ML models enhance scoring with predictive analytics and personalized recommendations.

### Enterprise Reliability

Built with patterns from large-scale distributed systems:

- **Circuit Breaker**: Prevents cascade failures
- **Batch Processor**: Optimizes Redis writes with priority queues
- **Multi-Layer Cache**: Reduces database load (>80% hit rate)
- **Health Monitoring**: Real-time system metrics
- **Graceful Degradation**: Fallback mechanisms for all critical paths

---

## 🚀 Usage

### For End Users

**Do not clone this repository.** Instead:

1. Visit [timekeeper.404connernotfound.dev](https://timekeeper.404connernotfound.dev)
2. Invite the bot to your Discord server
3. Server admins: Set up categories with `/admin categories add <name>`
4. Users: Start tracking with `/clockin <category>`

Full user documentation available at the website.

### For Developers (Reference Only)

This codebase is provided for **transparency and reference** only. It demonstrates:

- Enterprise Discord bot architecture
- Redis-based time tracking systems
- ML integration in Discord bots
- Advanced caching strategies
- Circuit breaker implementation
- Batch processing patterns

**This code is NOT intended to be run by third parties.** See [License](#license).

---

## 📋 Requirements

_For reference only - third-party deployment is not supported._

```txt
discord.py >= 2.0
python-dotenv
redis >= 4.0
PyNaCl
numpy
msgpack
cachetools
```

### Environment Variables

```env
DISCORD_AUTH_TOKEN=      # Bot token
REDIS_URL=               # Redis connection string
COMMAND_PREFIX=          # Legacy prefix (default: ".")
DEV_USER_ID=            # Developer Discord ID
```

---

## 🔧 System Architecture

### Data Flow

```
Discord User
    ↓ (Slash Command)
Commands Layer (timecard.py, admin.py, etc.)
    ↓
Business Logic (timekeeper.py)
    ↓
Multi-Layer Cache (L1→L2→L3)
    ↓
Batch Processor (priority queue)
    ↓
Redis (persistent storage)
```

### Key Design Decisions

1. **Redis as Primary Store**: Fast, atomic operations, built-in expiry
2. **Batch Processing**: Reduces write load, improves performance
3. **Multi-Tier Caching**: Hot data in memory, cold data in Redis
4. **Circuit Breaker**: Protects against Redis outages
5. **Shared Tracker Instance**: Single connection pool, resource efficient

---

## 📜 License

**Custom Restrictive License** (see LICENSE file)

**TL;DR**:

- ✅ You MAY view this code for learning/reference
- ✅ Anthropic's Code of Conduct applies
- ❌ You MAY NOT run this bot yourself
- ❌ You MAY NOT redistribute or resell this code
- ❌ You MAY NOT remove the hardware validation check
- ❌ No warranty, support, or liability

**This software includes hardware validation to ensure it runs only on authorized infrastructure.** Any attempt to bypass this is a license violation.

To use Timekeeper's features, invite the official bot from [timekeeper.404connernotfound.dev](https://timekeeper.404connernotfound.dev)

---

## 🤝 Contributing

**Code contributions are not accepted** as this is not an open-source project.

However, you can help by:

- 🐛 Reporting bugs in our Support Server
- 💡 Suggesting features via feedback channels
- 📚 Improving user documentation
- 🌟 Sharing Timekeeper with communities who might benefit

---

## 📊 Performance

Typical performance metrics:

- **Response Time**: <50ms average (cached), <200ms (cold)
- **Cache Hit Rate**: >85%
- **Batch Queue**: <1000 operations typical
- **Uptime**: 99.9%+ (circuit breaker protection)
- **Concurrent Users**: Tested to 10,000+

---

## 🔍 Monitoring

Built-in health monitoring tracks:

- Redis connectivity and latency
- Circuit breaker state
- Batch processor queue depth
- Cache performance (hit rates, sizes)
- Operation success rates
- Response time percentiles

Access via `/admin system` (admin only)

---

## 🙏 Acknowledgments

- **Original Timekeeper** - RIP 2025, your legacy continues
- **discord.py** - Rapptz and contributors
- **Redis** - The backbone of our data layer
- **Our Users** - For trusting us with your time tracking needs

---

## 📞 Support

- **Discord**: Join our Support Server
- **Email**: support@404connernotfound.dev
- **Website**: timekeeper.404connernotfound.dev
- **Issues**: This repo's Issues tab (viewing only)

---

**Built with ❤️ for productive teams everywhere**

_Timekeeper is not affiliated with Discord Inc._
