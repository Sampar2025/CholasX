# AI Building Materials Search - Backend API

This is the backend API for the WordPress AI Building Materials Search plugin.

## Quick Deploy to Railway

1. **Sign up at Railway**: https://railway.app/
2. **Create New Project** → "Deploy from GitHub repo"
3. **Upload these files** to a GitHub repository
4. **Connect the repository** to Railway
5. **Add Environment Variable**:
   - Variable: `PERPLEXITY_API_KEY`
   - Value: Your Perplexity API key
6. **Deploy** - Railway will automatically detect the Flask app

## Alternative: Deploy to Heroku

1. **Install Heroku CLI**
2. **Login**: `heroku login`
3. **Create app**: `heroku create your-app-name`
4. **Set environment variable**: `heroku config:set PERPLEXITY_API_KEY=your_key_here`
5. **Deploy**: `git push heroku main`

## Alternative: Deploy to Your Own Server

1. **Upload files** to your server
2. **Install Python 3.11+**
3. **Install dependencies**: `pip install -r requirements.txt`
4. **Set environment variable**: `export PERPLEXITY_API_KEY=your_key_here`
5. **Run**: `gunicorn app:app --bind 0.0.0.0:5000`

## Files Included

- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `Procfile` - For Railway/Heroku deployment
- `README.md` - This file

## API Endpoints

- `GET /` - Health check
- `POST /api/search` - Main search endpoint
- `GET /api/search/demo` - Demo endpoint with sample data

## Environment Variables Required

- `PERPLEXITY_API_KEY` - Your Perplexity API key
- `PORT` - Port to run on (automatically set by hosting services)

## Testing

Once deployed, test with:

```bash
curl -X POST https://your-app-url.railway.app/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "cheapest PIR board 50mm", "location": "UK", "max_results": 5}'
```

## WordPress Integration

Use the deployed URL in your WordPress plugin settings:
- Example: `https://your-app-name.railway.app`

## Support

If you encounter issues:
1. Check the deployment logs
2. Verify your Perplexity API key is valid
3. Ensure you have credits in your Perplexity account
4. Test the `/` endpoint to verify the app is running

