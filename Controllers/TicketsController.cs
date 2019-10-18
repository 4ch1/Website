using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using IIS.Models.Tickets;
using IIS.Queries;
using Microsoft.AspNetCore.Mvc;

namespace IIS.Controllers
{
    [Route("tickets")]
    public class TicketsController : Controller
    {
        private readonly SessionManager _sessionManager;

        public TicketsController(SessionManager manager)
        {
            _sessionManager = manager;
        }

        [HttpGet]
        [Route("buy")]
        public IActionResult Buy()
        {
            if (_sessionManager.GetCurrentUser().IsDummy)
                return RedirectToAction("Login", "Authentication");

            return View();
        }

        [HttpGet]
        [Route("getName")]
        public async Task<IActionResult> GetName(string term)
        {
            var result = await AirportQueries.GetAllAirports(term);
            return Json(result);
        }

        [HttpGet]
        [Route("search")]
        public async Task<IActionResult> Search([FromQuery]string Date, [FromQuery]string ToAirportLocation, [FromQuery]string FromAirportLocation)
        {
            return View(await GetTickets(FromAirportLocation, ToAirportLocation, Date));
        }

        private async Task<IEnumerable<Ticket>> GetTickets(string fromAirport, string toAirport, string date)
        {
            return await TicketQueries.GetAllTickets(fromAirport, toAirport, date);
        }

        [HttpGet]
        [Route("getShort")]
        public async Task<IActionResult> GetShort(string term)
        {
            var result = await AirportQueries.GetAllAirportsShort(term);
            return Json(result);
        }
    }
}