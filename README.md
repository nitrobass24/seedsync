# nitrobass24/seedsync
A Seedsync container running on Ubuntu 18.04

[SeedSync](https://github.com/ipsingh06/seedsync) is a GUI-configurable, LFTP-based file transfer and management program.
With a LFTP backend, it can fetch files from a remote server (like your seedbox) at maximum throughput.
Fully GUI-configurable means not having to muck around with scripts.
SeedSync also allows you to extract archives and delete files on both the local machine and the remote server,
all from the GUI!

![](https://user-images.githubusercontent.com/12875506/37031587-3a5df834-20f4-11e8-98a0-e42ee764f2ea.png)

## Usage

```
docker create \
	--name seedsync \
	-p 8800:8800 \
	-e USERNAME=<username>
	-e UID=<UID> \
	-e GID=<GID> \
	-e TZ=<timezone> \ 
	-v </path/to/appdata>:/config \
	-v <path/to/downloads>:/downloads \
	nitrobass24/seedsync
```

You can choose between ,using tags, various branch versions of sonarr, no tag is required to remain on the main branch.

Add one of the tags,  if required,  to the linuxserver/sonarr line of the run/create command in the following format, linuxserver/sonarr:develop

#### Tags

+ **develop**

## Parameters

`The parameters are split into two halves, separated by a colon, the left hand side representing the host and the right the container side. 
For example with a port -p external:internal - what this shows is the port mapping from internal to external of the container.
So -p 8800:80 would expose port 8800 from inside the container to be accessible from the host's IP on port 8800
http://192.168.x.x:8800 would show you what's running INSIDE the container on port 8800.`


* `-p 8800` - the port sonarr webinterface
* `-v /config` - seedsync configs
* `-v /downloads` - location where you want downloads stored
* `-e TZ` for timezone information, America/Chicago (default)
* `-e GID` for for GroupID - see below for explanation
* `-e UID` for for UserID - see below for explanation

## Localtime

It is important that you set the TZ variable. See [Localtime](#localtime) for important information

### User / Group Identifiers

Sometimes when using data volumes (`-v` flags) permissions issues can arise between the host OS and the container. We avoid this issue by allowing you to specify the user `UID` and group `GID`. Ensure the data volume directory on the host is owned by the same user you specify and it will "just work" <sup>TM</sup>.

In this instance `UID=1001` and `GID=1001`. To find yours use `id user` as below:

```
  $ id <dockeruser>
    uid=1001(dockeruser) gid=1001(dockergroup) groups=1001(dockergroup)
```

## Setting up the application
Access the webui at `<your-ip>:8800`, for more information check out [SeedSync](https://github.com/ipsingh06/seedsync).
