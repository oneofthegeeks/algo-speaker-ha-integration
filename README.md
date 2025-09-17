# Algo Speaker Home Assistant Integration

[![CI](https://github.com/yourusername/algo-speaker-ha-integration/workflows/CI/badge.svg)](https://github.com/yourusername/algo-speaker-ha-integration/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)

This integration allows you to control Algo IP speakers (8180, 8189, 8188, 8196) from Home Assistant using their REST API with HMAC authentication.

## 📋 Table of Contents

- [Features](#-features)
- [Supported Models](#-supported-algo-speaker-models)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Endpoints](#-api-endpoints-used)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## Features

- **Audio Control**: Play tones, announcements, and custom audio files
- **Strobe Lights**: Control strobe patterns and colors (if supported by your model)
- **Volume Control**: Adjust speaker volume
- **Multiple Alert Types**: Door bell, emergency alerts, page notifications, custom tones
- **Secure Authentication**: HMAC-SHA256 authentication for API security
- **Easy Configuration**: Simple setup with input controls and buttons

## Supported Algo Speaker Models

- **8180**: Basic IP speaker
- **8188**: IP speaker with additional features  
- **8189**: IP speaker with enhanced capabilities
- **8196**: Advanced IP speaker with full feature set

## Prerequisites

1. Algo speaker firmware version 3.3 or higher
2. NTP enabled on the Algo device
3. RESTful API enabled in Algo device settings
4. Home Assistant Supervised installation

## Installation

### 1. Upload Python Scripts

Place the `algo_speaker_integration.py` file in your Home Assistant `python_scripts/` directory.

### 2. Update Configuration

Add the contents of `configuration.yaml` to your Home Assistant `configuration.yaml` file.

**Important**: Replace `YOUR_SPEAKER_IP` with your actual Algo speaker IP address in all REST command URLs.

### 3. Add Automations

Add the contents of `automations.yaml` to your Home Assistant `automations.yaml` file.

### 4. Create Dashboard (Optional)

Add the Lovelace dashboard configuration to create a dedicated control panel for your Algo speakers.

## Configuration

### Basic Setup

1. **Get Speaker IP**: Find your Algo speaker's IP address from your router or Algo device settings
2. **Update IP Address**: Replace `YOUR_SPEAKER_IP` in all configuration files
3. **Set API Password**: The default password is "algo" - change this in the Algo device settings
4. **Upload Audio Files**: Upload your desired audio files to the Algo speaker

### Audio Files

Upload these audio files to your Algo speaker:
- `door-bell.wav`
- `emergency-alert.wav` 
- `page-notif.wav`
- `test-tone-1.wav`
- `test-tone-2.wav`

### API Authentication

The integration uses HMAC-SHA256 authentication. The Python script automatically generates the required authentication headers for each API call.

## Usage

### Manual Control

1. **Trigger Alert**: Use the "Trigger Alert" button to play the selected alert type
2. **Stop Alert**: Use the "Stop Alert" button to stop all current alerts
3. **Quick Actions**: Use the quick action buttons for common alert types
4. **Volume Control**: Adjust volume using the volume slider
5. **Strobe Control**: Configure strobe patterns, colors, and brightness

### Automation Examples

The integration includes several example automations:

- **Door Sensor**: Trigger door bell when door opens
- **Motion Sensor**: Play notification when motion detected
- **Time-based**: Daily announcements at specific times
- **Emergency**: Automatic emergency alerts from smoke detectors, water leaks, etc.

### Custom Alerts

You can create custom alert types by:

1. Adding new scripts in `configuration.yaml`
2. Creating new automations in `automations.yaml`
3. Using the custom tone input for specific audio files

## API Endpoints Used

- `GET /api/settings/device.info` - Device information
- `GET /api/settings/audio.page.vol` - Current volume
- `PUT /api/settings/audio.page.vol` - Set volume
- `POST /api/controls/tone/start` - Play tone
- `POST /api/controls/tone/stop` - Stop tone
- `POST /api/controls/strobe/start` - Start strobe
- `POST /api/controls/strobe/stop` - Stop strobe

## Troubleshooting

### Common Issues

1. **Connection Failed**: Check IP address and network connectivity
2. **Authentication Error**: Verify API password and time synchronization
3. **Audio Not Playing**: Check audio file exists on speaker and volume is set
4. **Strobe Not Working**: Verify your speaker model supports strobe lights

### Debug Steps

1. Check Home Assistant logs for REST command errors
2. Verify Algo speaker is accessible via web interface
3. Test API calls manually using the Python script
4. Ensure NTP is enabled on the Algo device

### Logs

Check these logs for troubleshooting:
- Home Assistant logs: `Configuration > Logs`
- Algo speaker logs: Device web interface > Logs

## Security Notes

- Change the default API password from "algo"
- Use HTTPS if possible (requires certificate setup)
- Consider network segmentation for security
- Regularly update Algo speaker firmware

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For issues with:
- **Home Assistant**: Check [Home Assistant community forums](https://community.home-assistant.io/)
- **Algo Speakers**: Contact [Algo support](mailto:support@algosolutions.com)
- **This Integration**: 
  - Check the [Issues](https://github.com/yourusername/algo-speaker-ha-integration/issues) section
  - Review the configuration files and logs
  - Create a new issue with detailed information

## 📚 Additional Resources

- [Algo Solutions Documentation](https://docs.algosolutions.com/)
- [Home Assistant RESTful Command Documentation](https://www.home-assistant.io/integrations/rest_command/)
- [Home Assistant REST Sensor Documentation](https://www.home-assistant.io/integrations/rest/)

## ⭐ Star this Repository

If you find this integration useful, please consider giving it a star on GitHub!
