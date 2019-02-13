#!/usr/bin/python3
import hashlib
import getpass

def main():
    pass1 = getpass.getpass("Enter new password (min. 8 characters): ")
    if pass1 is None or len(pass1) < 8:
        print("Password too small.")
        return
    pass2 = getpass.getpass("Repeat password: ")
    if pass2 != pass1:
        print("Passwords do not match!")
        return
    
    password = pass1.encode("utf-8")
    salt = "bythepowerofgrayskull".encode("utf-8")
    hash_obj = hashlib.sha256(password + salt)
    key = hash_obj.digest()
    with open(".key", "w+b") as keyfile:
        keyfile.write(bytes(key))

    print("Done and done.")

if __name__ == '__main__':
    main()
