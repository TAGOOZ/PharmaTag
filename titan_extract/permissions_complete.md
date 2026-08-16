# TITAN.W1 - Complete User Permission System

## 1. USER TYPES / LEVELS

### Primary User Types
| Type | Description |
|------|-------------|
| **Super Admin** | Full system access, can login as any user |
| **Admin** | Administrative permissions, can manage users |
| **Pharmacy Manager** | Management-level access to pharmacy operations |
| **Technical Support** | Limited access for technical support purposes |
| **Operations Account** | Access to daily operations (sales, purchases) |
| **Management Account** | Access to management reports and settings |
| **Normal User** | Standard user with limited permissions |
| **Cashier** | Sales-focused user (inferred from cashier operations) |

### User Level Hierarchy
- **Level 1**: Super Admin / Admin (highest)
- **Level 2**: Pharmacy Manager / Technical Support
- **Level 3**: Operations / Management accounts
- **Level 4**: Normal User / Cashier (lowest)

### User Group System
- `<iGroupId> 2 </iGroupId>` - Group ID field in user records
- `<iLevel> 1 </iLevel>` - Level field in user records
- Groups can contain multiple pharmacies/stores

## 2. PERMISSION FLAGS / CATEGORIES

### Core Permission Operations
| Permission | Description |
|------------|-------------|
| `*AddNewUser*` | Can add new users to the system |
| `*ChangeUserAuths*` | Can change user authorizations/permissions |
| `*USER!*` | User management operations |

### Login Types
| Login Type | Description |
|------------|-------------|
| `Login as super admin` | Full system access |
| `Login one time` | One-time login without persistent session |
| `Login with management account` | Management-level access |
| `Login with operations account` | Operations-level access |
| `Log in as Technical Support` | Technical support access |
| `Log in as a manager without logging off current user` | Manager access without logout |

### Permission Categories
1. **Sales Permissions**
   - Can sell drugs
   - Can process returns
   - Can apply discounts
   - Can void transactions
   - Can edit prices
   - Can override prices

2. **Purchase Permissions**
   - Can buy/purchase drugs
   - Can import from other pharmacies
   - Can process purchase returns
   - Can edit purchase prices

3. **Inventory Permissions**
   - Can edit stock
   - Can transfer between branches
   - Can receive transfers
   - Can export inventory
   - Can import inventory

4. **Report Permissions**
   - Can view reports
   - Can print reports
   - Can export reports
   - Can access financial reports
   - Can access sales reports
   - Can access purchase reports

5. **Settings Permissions**
   - Can modify pharmacy settings
   - Can change printer settings
   - Can modify barcode settings
   - Can change company information
   - Can modify tax/VAT settings

6. **User Management Permissions**
   - Can add users
   - Can edit users
   - Can delete users
   - Can change passwords
   - Can reset passwords
   - Can view user activity

## 3. PASSWORD HANDLING

### Password Features
- `Change password` - User can change their own password
- `Change Password` - System function for password change
- `change my password` - Quick password change option
- `forgot my password` - Password recovery option
- `Forgot password` - Password recovery flow
- `Password is empty.` - Validation message
- `Password required` - Validation message
- `Invalid Username or Password.` - Authentication error
- `Invalid password` - Authentication error
- `Wrong password !` - Authentication error
- `wrong password !` - Authentication error

### Password Storage
- Passwords stored in database tables
- `Password Code = ` - Password code reference
- `input report password 9******4` - Report access password
- `input database password` - Database access password
- `input your ftp username` - FTP access credentials

### Password Reset
- `New password Now is   3030` - Default password example
- `forgot my password` - Password recovery flow
- `Forgot password` - Password recovery option

## 4. USER LOGIN/LOGOUT FLOW

### Login Process
1. User enters username and password
2. System validates credentials against database
3. System checks user status (active/passive/blocked)
4. System loads user permissions
5. System creates session
6. User is redirected to main menu

### Login Strings
- `Username` - Username field
- `Username cannot be null.` - Validation
- `Username is empty or invalid` - Validation
- `Username is empty.` - Validation
- `Password` - Password field
- `Invalid Username or Password.` - Authentication error
- `Invalid user.` - Authentication error

### Logout Process
1. System closes user session
2. System clears user permissions
3. System returns to login screen

### Session Management
- `Log in as a manager without logging off current user` - Manager session overlay
- `Login one time` - One-time login without persistent session
- `Session` - Session management

## 5. ONE-TIME LOGIN USERS

### One-Time Login Features
- `Login one time` - One-time login option
- `Temporary activation for 3 days` - Temporary access
- `TRial No:  ` - Trial number reference
- `Trial No : ` - Trial number display

### Temporary Access
- `Your user has been temporarily blocked. Please try again later` - Temporary block
- `Your account is deactivated. Apply to your system manager.` - Deactivation message

## 6. USER GROUPS AND HIERARCHIES

### Group System
- Users can be organized into groups
- Groups can contain multiple pharmacies
- `Add  group pharmacies ` - Add pharmacies to group
- `Add group pharmacies` - Group management
- `Group by datee` - Grouping by date
- `Grouping items received from a specific supplier` - Supplier grouping

### Hierarchy Levels
1. **System Level** (Super Admin)
   - Full system access
   - Can manage all pharmacies
   - Can manage all users

2. **Pharmacy Level** (Pharmacy Manager)
   - Pharmacy-specific access
   - Can manage pharmacy users
   - Can manage pharmacy settings

3. **Department Level** (Operations/Management)
   - Department-specific access
   - Can manage department operations
   - Can view department reports

4. **User Level** (Normal User)
   - Limited access
   - Can perform assigned tasks
   - Can view assigned reports

## 7. USER AUTHORIZATION TABLE

### TitanUserAction Table
```sql
INSERT INTO TitanUserAction(drugname,typevalue,oldvalue,newvalue,mobile,namee,curbarcode,curprice,units,datee)
```

### User Activity Tracking
- `Users loading ..` - User loading message
- `Inquiry about employee sales` - Employee sales inquiry
- `Follow up sales operations on Titan` - Sales tracking
- `Sort your employees according to the degree of trust` - Trust-based sorting

## 8. USER MANAGEMENT FORMS

### FFFUserEdit Form
- User editing form with 18 procedures
- Edit user details
- Change user permissions
- Reset user passwords
- View user activity

### FFFUserChoose Form
- User selection form with 19 procedures
- Select user for assignment
- View user details
- Filter users by group

## 9. PERMISSION CHECKS IN CODE

### Authorization Checks
- `Stakeholder is unauthorized for this operation` - Operation unauthorized
- `The stakeholder is not authorized to supply for this drug.` - Supply unauthorized
- `This stakeholder is not authorized for human drugs.` - Human drugs unauthorized
- `This stakeholder is not authorized for veterinary drugs.` - Veterinary drugs unauthorized
- `User is not authorized for this service. Apply to your firm.` - Service unauthorized
- `You are not authorized to use this service.` - General unauthorized

### Block/Deactivate Checks
- `Block app from this path` - App blocking
- `Block barcode from usage` - Barcode blocking
- `Block cancel operation is unsuccessful.` - Block operation error
- `Block operation has already been cancelled.` - Block operation status
- `Block operation has already been recalled.` - Block operation status
- `Block operation has been recalled` - Block operation status
- `Block operation to be recalled is unsuccessful.` - Block operation error
- `Define barcodes block` - Barcode blocking setup
- `Download duplicated barcode blocking tool` - Blocking tool
- `Cancel barcode blocking` - Unblock barcodes

### User Status Checks
- `Your account is deactivated. Apply to your system manager.` - Deactivated account
- `Your user has been temporarily blocked. Please try again later` - Temporarily blocked
- `Sender user is passive` - Passive sender
- `Sender stakeholder is passive` - Passive stakeholder
- `Receiver stakeholder is passive.` - Passive receiver
- `Indicated seller is deactivated` - Deactivated seller
- `Status of this drug is passive` - Passive drug status

### Authentication Checks
- `Invalid authentication code` - Invalid auth code
- `Invalid block level` - Invalid block level
- `Invalid level information.` - Invalid level
- `Invalid recall level` - Invalid recall level
- `Invalid deactivation reason` - Invalid deactivation reason

## 10. USER ACTIVITY LOGGING

### User Action Table
```sql
CREATE TABLE TitanUserAction(
    drugname varchar(200),
    typevalue int,
    oldvalue varchar(100),
    newvalue varchar(100),
    mobile varchar(20),
    namee varchar(100),
    curbarcode varchar(50),
    curprice float,
    units int,
    datee datetime
)
```

### ChainBuyUsers Table
```sql
CREATE TABLE ChainBuyUsers(
    PharmacistTel varchar(20),
    -- Additional fields for chain pharmacy users
)
```

### User Source Update Table
```sql
CREATE TABLE usersourceupdate(
    drugname varchar(200),
    price float,
    units int,
    localimport int,
    -- Additional fields for user source updates
)
```

## 11. PASSWORD RECOVERY

### Recovery Flow
1. User clicks "Forgot password"
2. System prompts for verification
3. System sends recovery code
4. User enters code
5. System allows password reset

### Recovery Messages
- `Forgot password` - Recovery option
- `forgot my password` - Recovery option
- `Password Code = ` - Recovery code reference
- `Call us telegram 01015441306  - Password Code = ` - Contact for recovery
- `Tel=01030918711 telegram Password Code = ` - Contact for recovery

## 12. USER INTERFACE PERMISSIONS

### Menu Visibility
- Menu items shown/hidden based on user permissions
- `Modify staff settings` - Staff settings access
- `Modify customer settings` - Customer settings access
- `Modify suppliers settings` - Supplier settings access

### Button States
- Buttons enabled/disabled based on permissions
- `AllowUserResizing` - Allow user to resize windows

### Report Access
- Reports filtered by user permissions
- `input report password 9******4` - Report access password
- `Reports` - Report access
- `report not found` - Report access error
