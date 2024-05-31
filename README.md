# QUIC Chat

1. Install dependencies with pip (requirements.txt) is provided
2. run `python3 echo.py server` to start the server
3. run `python3 echo.py client -u YOUR_USERNAME`, you can replace YOUR_USERNAME with anything
4. run `python3 echo.py client -u YOUR_USERNAME2`. you can also use anything, as long as it is different than step 3

Note:
If on a custom ip, you can start the server using:
`python3 echo.py server -l YOUR_IP_ADDRESS -p YOUR_PORT`

and start the clients with:
`python3 echo.py client -s YOUR_SERVER_IP_ADDRESS -p YOUR_PORT -u YOUR_USERNAME`



Correct output for server:
```sh
[svr] Server starting...
```


Correct output for clients:

```sh
[cli-YOUR_USERNAME] starting client
[cli-YOUR_USERNAME] Enter message:
```
