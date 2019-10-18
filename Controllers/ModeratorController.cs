using System.Threading.Tasks;
using IIS.Models.Tickets;
using IIS.Queries;
using Microsoft.AspNetCore.Mvc;

namespace IIS.Controllers
{
    [Route("moderator")]
    public class ModeratorController : Controller
    {
        private readonly SessionManager _sessionManager;

        public ModeratorController(SessionManager manager)
        {
            _sessionManager = manager;
        }

        [HttpGet]
        [Route("add")]
        public IActionResult AddFlight()
        {
            return View();
        }

        [HttpPost]
        [Route("add")]
        public async Task<IActionResult> AddFlight([FromForm]string Date, [FromForm]string ToAirportShort,
            [FromForm]string FromAirportShort, [FromForm]string time, [FromForm]string category, [FromForm]string price)
        {
            await TicketQueries.Add(Date, ToAirportShort, FromAirportShort, time, category,
                 (await _sessionManager.GetCurrentUser().GetCompany()).FullName, price);

            return View();
        }

        [HttpGet]
        [Route("dashboard")]
        public async Task<IActionResult> DashBoard()
        {
            return View(await TicketQueries.GetAllTickets((await _sessionManager.GetCurrentUser().GetCompany()).FullName));
        }

        [HttpPost]
        [Route("save")]
        public IActionResult Save()
        {
            return Ok();
        }

        [HttpGet]
        [Route("edit")]
        public async Task<IActionResult> EditTicket(long id)
        {
            return View(await TicketQueries.GetTicket(id));
        }

        [HttpPost]
        [Route("edit")]
        public async Task<IActionResult> EditTicket([FromForm]string id, [FromForm]string delete, [FromForm]string save, [FromForm]string date, [FromForm]string category, [FromForm]string price)
        {
            if (!string.IsNullOrEmpty(delete))
                await TicketQueries.Delete(id);


            if (!string.IsNullOrEmpty(save))
                await TicketQueries.Update(id, date, category, price);

            return View("DashBoard", await TicketQueries.GetAllTickets((await _sessionManager.GetCurrentUser().GetCompany()).FullName));
        }
    }
}