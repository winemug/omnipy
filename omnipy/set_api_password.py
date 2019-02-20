#!/usr/bin/python3
import hashlib
import getpass
import podcomm.definitions

def main():

    while True:
        pass1 = getpass.getpass("Enter new password (min. 8 characters): ")
        if pass1 is None or len(pass1) < 8:
            print("Password is less than 8 characters long")
            continue
        pass2 = getpass.getpass("Repeat password: ")
        if pass2 != pass1:
            print("Passwords do not match!")
            continue
        
        try:
            password = pass1.encode("utf-8")
            salt = "bythepowerofgrayskull".encode("utf-8")
            hash_obj = hashlib.sha256(password + salt)
            key = hash_obj.digest()
            with open(".key", "w+b") as keyfile:
                keyfile.write(bytes(key))
        except Exception as e:
            getLogger().error("Error while creating and saving password: %s" % e)
            raise
            print("Password has been set.")
            return

if __name__ == '__main__':
    configurelogging()
    main()
