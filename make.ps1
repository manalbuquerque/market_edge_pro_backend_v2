param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("up","down","mig","seed","test","fmt","help")]
    [string]$cmd
)

switch ($cmd) {
    "up" {
        Write-Host "▶ Starting stack..."
        docker compose up -d --build
    }
    "down" {
        Write-Host "🛑 Stopping stack..."
        docker compose down -v
    }
    "mig" {
        Write-Host "📦 Running migrations..."
        docker compose run --rm app alembic upgrade head
    }
    "seed" {
        Write-Host "🌱 Seeding database..."
        docker exec -i mep-db psql -U postgres -d market_edge -f /docker-entrypoint-initdb.d/01-seeds.sql
    }
    "test" {
        Write-Host "🧪 Running tests..."
        docker compose run --rm app pytest -v
    }
    "fmt" {
        Write-Host "✨ Formatting code..."
        docker compose run --rm app black .; docker compose run --rm app isort .
    }
    "help" {
        Write-Host "Available commands:"
        Write-Host "  .\make.ps1 up    # start stack"
        Write-Host "  .\make.ps1 down  # stop & remove"
        Write-Host "  .\make.ps1 mig   # run migrations"
        Write-Host "  .\make.ps1 seed  # load dev data"
        Write-Host "  .\make.ps1 test  # run tests"
        Write-Host "  .\make.ps1 fmt   # lint/format"
    }
}
