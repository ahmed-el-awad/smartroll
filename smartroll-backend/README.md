# Running the backend

## Windows

Change to the backend directory

```bash
cd smartroll-backend
```

This assumes that the `venv` folder is not made (if it is, then skip this)

```bash
python -m venv venv
```

Run the virtual environment by running

```bash
.\venv\Scripts\activate
```

Install the dependencies

```bash
pip install -r .\requirements.txt
```

Run the server

```bash
python app.py
```

## MacOS

Change to the backend directory

```bash
cd smartroll-backend
```

This assumes that the `venv` folder is not made (if it is, then skip this)

```bash
python3 -m venv venv
```

Run the virtual environment by running

```bash
source venv/bin/activate
```

Install the dependencies

```bash
pip install -r requirements.txt
```

Run the server

```bash
python3 app.py
```
