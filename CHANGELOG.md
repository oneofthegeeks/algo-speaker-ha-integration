# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release
- Support for Algo speaker models: 8180, 8189, 8188, 8196
- HMAC-SHA256 authentication for API security
- Multiple alert types: door bell, emergency, page notification, custom tones
- Strobe light control (for supported models)
- Volume control
- Home Assistant REST commands and sensors
- Example automations
- Lovelace dashboard
- Python API integration class
- Comprehensive documentation

### Features
- **Audio Control**: Play tones, announcements, and custom audio files
- **Strobe Lights**: Control strobe patterns and colors
- **Volume Control**: Adjust speaker volume
- **Multiple Alert Types**: Various pre-configured alert scenarios
- **Secure Authentication**: HMAC-SHA256 authentication
- **Easy Configuration**: Simple setup with input controls and buttons
- **Smart Automations**: Door sensors, motion sensors, time-based alerts
- **Dashboard**: Beautiful Lovelace UI for manual control

### Technical Details
- REST API integration with Algo speakers
- Standard HMAC authentication (recommended by Algo)
- Support for firmware version 3.3+
- Home Assistant Supervised compatibility
- Python 3.8+ support

## [1.0.0] - 2024-01-XX

### Added
- Initial release of Algo Speaker Home Assistant Integration
- Complete integration package with all necessary files
- GitHub repository setup with CI/CD
- MIT License
- Contributing guidelines
- Comprehensive README documentation

---

## Version History

- **1.0.0**: Initial release with full feature set
- **Unreleased**: Development version with latest features

## Support

For support and questions:
- Create an issue on GitHub
- Check the README.md for setup instructions
- Review the troubleshooting section

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
