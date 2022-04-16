try:
    from exegol.manager.ExegolController import main
except ModuleNotFoundError as e:
    print("Mandatory dependencies are missing:", e)
    print("Please install them with pip3 install -r requirements.txt")
    exit(1)

if __name__ == "__main__":
    main()
