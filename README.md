# PNGTuber
I wrote PNGTuber to display my PNGTuber avatar. My avatar was created by [V0idless](https://www.twitch.tv/v0idlessart). She makes awesome art! :)

## Preview
![pngtuber_microphone](https://github.com/user-attachments/assets/387ab98d-2dfb-4f91-83ce-b136b090fbeb) ![pngtuber](https://github.com/user-attachments/assets/6f48af87-6a5b-4648-bc68-7573367dd08b)

## Configuration

The basic configuration is done via the `config.ini` file.

### config.ini

```ini
[app]
background_color = magenta
host = localhost
port = 8089

[default]
base_dir = default
ec_mc = ec_mc.png
ec_mo = ec_mo.png
eo_mc = eo_mc.png
eo_mo = eo_mo.png
```

### Description of the state attributes

Below you will find a description of the state attributes.

| Field  | Description |
| ------------- | ------------- |
| base_dir  | folder relativ to `config.ini`  |
| ec_mc  | eyes closed, mouth closed  |
| ec_mo  | eyes closed, mouth open  |
| eo_mc  | eyes open, mouth closed  |
| eo_mo  | eyes open, mouth open  |

## Layers support
PNGTuber supports multiple layers per state, which can be configured via `config.ini` and `layers.ini`. A pause can be configured between layer animations, either as a static number or as a range for the random number generator.

![scared2](https://github.com/user-attachments/assets/c348d128-aa82-461b-b39f-011de8b53ac1)

### Configuration

#### config.ini

```ini
[app]
background_color = magenta
host = localhost
port = 8089

[default]
base_dir = default
ec_mc = ec_mc.png
ec_mo = ec_mo.png
eo_mc = eo_mc.png
eo_mo = eo_mo.png

[scared]
base_dir = scared
ec_mc = ec_mc.png
ec_mo = ec_mo.png
eo_mc = eo_mc.png
eo_mo = eo_mo.png
layers = scared.flashlight, scared.icebreath
```

#### layers.ini

```ini
[scared.flashlight]
base_dir = scared
image = flashlight_anim.apng
loop_pause=10-30

[scared.icebreath]
base_dir = scared
image = icebreath.apng
loop_pause=5-10
```

#### Preview
The ice breath reappears after 5 to 10 seconds and the flickering of the light after 10 to 30 seconds.

![scared](https://github.com/user-attachments/assets/641da7d4-36a8-4d4c-9e68-4b672d1ffc83)

## Socket communication
### Samples
#### Talk

```bash
echo -ne "talk\r\n" | netcat localhost 8089 -w 0
```

#### Change state to state number 4

```bash
echo -ne "state:4\r\n" | netcat localhost 8089 -w 0
```

