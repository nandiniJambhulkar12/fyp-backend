# Setup Instructions for XAI Code Audit Dashboard

## Prerequisites

### 1. Install Node.js
You need to install Node.js first to run this React application:

1. **Download Node.js:**
   - Go to [https://nodejs.org/](https://nodejs.org/)
   - Download the LTS version (recommended)
   - Choose the Windows Installer (.msi)

2. **Install Node.js:**
   - Run the downloaded installer
   - Follow the installation wizard
   - Make sure to check "Add to PATH" during installation

3. **Verify Installation:**
   - Open a new Command Prompt or PowerShell window
   - Run: `node --version`
   - Run: `npm --version`
   - Both commands should return version numbers

## Project Setup

### 1. Install Dependencies
Once Node.js is installed, navigate to your project folder and install dependencies:

```bash
# Navigate to project directory
cd C:\Users\shrut\Desktop\ui

# Install all required packages
npm install
```

### 2. Start Development Server
```bash
npm start
```

### 3. Open in Browser
- The app will automatically open at `http://localhost:3000`
- If it doesn't open automatically, manually navigate to that URL

## Alternative Setup Methods

### Using Yarn (if you prefer)
```bash
# Install Yarn globally
npm install -g yarn

# Install dependencies
yarn install

# Start development server
yarn start
```

### Using pnpm (if you prefer)
```bash
# Install pnpm globally
npm install -g pnpm

# Install dependencies
pnpm install

# Start development server
pnpm start
```

## Troubleshooting

### Common Issues:

1. **"npm is not recognized"**
   - Node.js is not installed or not in PATH
   - Restart your terminal after installing Node.js
   - Try running as Administrator

2. **"Cannot find module" errors**
   - Dependencies not installed: Run `npm install`
   - Clear cache: `npm cache clean --force`
   - Delete `node_modules` folder and run `npm install` again

3. **Port 3000 already in use**
   - The app will automatically try port 3001, 3002, etc.
   - Or kill the process using port 3000

4. **TypeScript errors**
   - Make sure all dependencies are installed
   - Check that `tsconfig.json` is in the project root
   - Restart your IDE/editor

## Project Structure After Setup

```
ui/
├── node_modules/          # Dependencies (created after npm install)
├── public/               # Static files
├── src/                  # Source code
├── package.json          # Project configuration
├── tsconfig.json         # TypeScript configuration
├── tailwind.config.js    # TailwindCSS configuration
└── README.md            # Project documentation
```

## Available Scripts

After installation, you can use these commands:

- `npm start` - Start development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App (not recommended)

## Next Steps

1. Install Node.js from [nodejs.org](https://nodejs.org/)
2. Open Command Prompt/PowerShell as Administrator
3. Navigate to your project folder
4. Run `npm install`
5. Run `npm start`
6. Open `http://localhost:3000` in your browser

The TypeScript errors you're seeing will be resolved once the dependencies are installed!